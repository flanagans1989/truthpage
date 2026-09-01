"""Getting a new tenant from an empty account to a live trust page.

Two ways in, both landing in the same place:

  * the picker — 32 providers whose sub-processor URLs are already known, so
    adding five of them is five checkboxes rather than five URL hunts;
  * the importer — the tenant pastes their own privacy policy (a URL or the
    text) and the extractor reads the vendor names out of it.

The importer's hard part is not extraction, it is what to do with a name.
A name alone cannot be monitored — monitoring needs the vendor's own policy
URL. So an extracted name is only offered as ready-to-add when the library
knows that vendor; everything else is handed back as "we found this, give us
its URL". Guessing a URL from a name would point a tenant's monitoring at
the wrong company's page and they would never know.
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.extractor import SubProcessorExtractor
from app.core.provider_library import BY_SLUG, match_provider, normalise_name
from app.core.scraper.fetcher import BotWallError, fetch_html_fast
from app.core.scraper.normalizer import HTMLNormalizer
from app.core.urlguard import validate_url
from app.db.models.subprocessor import Subprocessor

logger = logging.getLogger(__name__)

_normalizer = HTMLNormalizer()
_extractor = SubProcessorExtractor()

# A privacy policy is long and the vendor list is rarely at the very end, but
# the extractor's own cap is 40k; this one keeps a pathological paste from
# reaching it at all.
MAX_PASTE_CHARS = 60_000


@dataclass
class Candidate:
    """One vendor name the importer found in the tenant's own policy."""

    name: str
    purpose: str = ""
    slug: str | None = None       # library row, when we recognised the name
    url: str | None = None        # monitoring URL, only ever from the library
    already_added: bool = False

    @property
    def ready(self) -> bool:
        """Addable with one click: recognised, and not already monitored."""
        return self.url is not None and not self.already_added


@dataclass
class ImportResult:
    candidates: list[Candidate] = field(default_factory=list)
    error: str | None = None

    @property
    def ready(self) -> list[Candidate]:
        return [c for c in self.candidates if c.ready]

    @property
    def needs_url(self) -> list[Candidate]:
        return [c for c in self.candidates if c.url is None]

    @property
    def already_added(self) -> list[Candidate]:
        return [c for c in self.candidates if c.already_added]


async def existing_keys(tenant_id, db: AsyncSession) -> set[str]:
    """Normalised names of what this tenant already monitors.

    Compared on the name rather than the URL: a tenant who typed "Stripe" by
    hand against a different Stripe URL has still added Stripe, and the
    importer offering it again would look broken.
    """
    rows = (
        await db.execute(
            select(Subprocessor.name).where(Subprocessor.tenant_id == tenant_id)
        )
    ).scalars().all()
    return {normalise_name(name) for name in rows}


def build_candidates(entries: list[dict], existing: set[str]) -> list[Candidate]:
    """Extracted rows → candidates, de-duplicated and library-matched."""
    seen: set[str] = set()
    candidates: list[Candidate] = []
    for entry in entries:
        name = (entry.get("name") or "").strip()
        key = normalise_name(name)
        if not key or key in seen:
            continue
        seen.add(key)

        provider = match_provider(name)
        candidates.append(
            Candidate(
                # The library's spelling wins when we recognised the vendor:
                # "AWS" in a policy should land in the list as the same name
                # the picker would have used, or the tenant sees two of it.
                name=provider["name"] if provider else name,
                purpose=(entry.get("purpose") or "").strip(),
                slug=provider["slug"] if provider else None,
                url=provider["url"] if provider else None,
                already_added=(
                    key in existing
                    or (provider is not None and normalise_name(provider["name"]) in existing)
                ),
            )
        )
    # Ready first, then the ones needing a URL, then what they already have —
    # the order the tenant works through them in.
    return sorted(candidates, key=lambda c: (c.already_added, c.url is None, c.name.lower()))


async def policy_text(*, url: str | None, pasted: str | None) -> str:
    """The document to extract from, whichever way the tenant supplied it."""
    if pasted and pasted.strip():
        return pasted.strip()[:MAX_PASTE_CHARS]
    if not url or not url.strip():
        raise ValueError("Give us a policy URL or paste the text.")

    url = url.strip()
    await validate_url(url)
    html = await fetch_html_fast(url)
    text = _normalizer.normalize(html)
    if len(text) < 200:
        raise ValueError(
            "That page had almost no readable text — it may render with "
            "JavaScript. Paste the vendor list instead."
        )
    return text[:MAX_PASTE_CHARS]


async def import_candidates(
    *, url: str | None, pasted: str | None, tenant_id, db: AsyncSession
) -> ImportResult:
    """Fetch-or-read, extract, match. Never raises at the caller."""
    try:
        text = await policy_text(url=url, pasted=pasted)
    except BotWallError:
        return ImportResult(
            error=(
                "That page blocked our fetch. Open it in your browser, copy "
                "the vendor list and paste it below — that works just as well."
            )
        )
    except ValueError as exc:
        return ImportResult(error=str(exc))
    except Exception:
        logger.exception("Import: could not read the source document")
        return ImportResult(error="We could not read that page. Try pasting the text instead.")

    try:
        extraction = await _extractor.extract(text)
    except Exception:
        logger.exception("Import: extraction failed")
        return ImportResult(error="The importer is busy. Try again in a moment.")

    entries = [e.model_dump() for e in extraction.entries]
    if not entries:
        return ImportResult(
            error=(
                "No sub-processors could be read from that text. If the list "
                "lives on a separate page, point us at that page instead."
            )
        )

    existing = await existing_keys(tenant_id, db)
    result = ImportResult(candidates=build_candidates(entries, existing))
    logger.info(
        "Import: %d extracted, %d ready, %d need a URL, %d already added",
        len(entries), len(result.ready), len(result.needs_url), len(result.already_added),
    )
    return result


@dataclass
class AddResult:
    added: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # already monitored
    refused: list[str] = field(default_factory=list)   # over the plan cap


async def add_providers(
    slugs: list[str], tenant, db: AsyncSession
) -> AddResult:
    """Add library providers to a tenant, honouring the plan cap.

    Partial success is the point: picking eight on a three-page free plan adds
    three and says so, rather than failing the whole submission and leaving a
    new tenant with an empty account.
    """
    existing = await existing_keys(tenant.id, db)
    count = len(existing)
    limit = tenant.subprocessor_limit
    result = AddResult()

    for slug in slugs:
        provider = BY_SLUG.get(slug)
        if provider is None:
            continue
        key = normalise_name(provider["name"])
        if key in existing:
            result.skipped.append(provider["name"])
            continue
        if count >= limit:
            result.refused.append(provider["name"])
            continue
        db.add(
            Subprocessor(
                tenant_id=tenant.id,
                name=provider["name"],
                monitored_url=provider["url"],
                check_interval_minutes=1440,
            )
        )
        existing.add(key)
        count += 1
        result.added.append(provider["name"])

    if result.added:
        await db.commit()
    logger.info(
        "Onboarding: tenant %s added %d, skipped %d, refused %d (cap %d)",
        tenant.slug, len(result.added), len(result.skipped), len(result.refused), limit,
    )
    return result
