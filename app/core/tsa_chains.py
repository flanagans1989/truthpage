"""Maps a TSA's authority URL to its bundled CA chain file under
certs/tsa/ (see that directory's README — files there are never deleted).

Used by both app/services/evidence.py (which chain to embed in a freshly
timestamped pack) and app/services/verify.py (which chain to check an
uploaded pack's token against) — one lookup, not two copies that could
disagree about where a given authority's chain lives.
"""
from pathlib import Path
from urllib.parse import urlparse

_CERTS_DIR = Path(__file__).parent.parent.parent / "certs" / "tsa"


def chain_filename_for_authority(tsa_authority_url: str | None) -> str | None:
    """'freetsa.org.pem' for 'https://freetsa.org/tsr', or None if the URL
    is empty/unparseable or no file exists for that host — the caller
    decides what "no chain available" means for its situation; this never
    guesses or falls back to a different authority's chain."""
    if not tsa_authority_url:
        return None
    host = urlparse(tsa_authority_url).hostname
    if not host:
        return None
    filename = f"{host}.pem"
    return filename if (_CERTS_DIR / filename).is_file() else None


def chain_path_for_authority(tsa_authority_url: str | None) -> Path | None:
    filename = chain_filename_for_authority(tsa_authority_url)
    return (_CERTS_DIR / filename) if filename else None


def all_bundled_chain_paths() -> list[Path]:
    """Every chain file we hold, regardless of authority — used only where
    no manifest names which authority to check against (the file+token
    pair upload mode in /verify has no manifest at all)."""
    return sorted(_CERTS_DIR.glob("*.pem"))
