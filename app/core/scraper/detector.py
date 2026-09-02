import difflib

# How much of a diff the classifier is allowed to see. Roughly 3k tokens —
# the limit is cost and latency, not model capability.
DIFF_FOR_LLM_MAX_CHARS = 12_000


class ChangeDetector:
    """Produces a human-readable unified diff between two normalized texts."""

    def unified_diff(self, old_text: str, new_text: str, label: str = "content") -> str:
        # keepends=False: the normalized text carries "\n" as a real line
        # separator now (see normalizer.py), and keeping the terminators
        # while also joining the diff with "\n" doubles every blank line.
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{label}:before",
            tofile=f"{label}:after",
            lineterm="",
        )
        return "\n".join(diff)


def diff_for_llm(raw_diff: str, max_chars: int = DIFF_FOR_LLM_MAX_CHARS) -> str:
    """Trim a diff to something the classifier can afford, by whole hunks.

    The old behaviour was raw_diff[:12_000] — a blind head-crop. With a
    one-line diff that meant the model saw the opening of the deleted
    document and none of the added one; even now, on a long page, a plain
    head-crop would reliably hide a change that happens to sit near the
    bottom (which is where a sub-processor table usually is). A page's
    biggest vendors are its longest pages, so the crop was worst exactly
    where the stakes were highest.

    Hunks are what carry the change, so hunks are the unit: keep whole ones
    from the start and the end, and say plainly how many were dropped in
    between. An honest "N hunks omitted" also gives the model grounds to
    answer UNCERTAIN, which routes to human review — far better than
    confidently classifying a fragment it cannot see the rest of.
    """
    if len(raw_diff) <= max_chars:
        return raw_diff

    lines = raw_diff.split("\n")
    header: list[str] = []
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            body_start = i
            break
        header.append(line)
    else:
        # No hunk markers at all — nothing structural to preserve.
        return raw_diff[:max_chars]

    hunks: list[list[str]] = []
    for line in lines[body_start:]:
        if line.startswith("@@"):
            hunks.append([line])
        elif hunks:
            hunks[-1].append(line)

    header_text = "\n".join(header)
    budget = max_chars - len(header_text) - 100  # room for the omission notice
    if budget <= 0:
        return raw_diff[:max_chars]

    kept_head: list[list[str]] = []
    kept_tail: list[list[str]] = []
    used = 0
    left, right = 0, len(hunks) - 1
    take_head = True
    while left <= right:
        index = left if take_head else right
        text = "\n".join(hunks[index])
        if used + len(text) + 1 > budget:
            break
        used += len(text) + 1
        if take_head:
            kept_head.append(hunks[index])
            left += 1
        else:
            kept_tail.insert(0, hunks[index])
            right -= 1
        take_head = not take_head

    omitted = len(hunks) - len(kept_head) - len(kept_tail)
    parts = [header_text]
    parts += ["\n".join(h) for h in kept_head]
    if omitted > 0:
        parts.append(f"[... {omitted} further changed section(s) omitted ...]")
    parts += ["\n".join(h) for h in kept_tail]
    return "\n".join(parts)
