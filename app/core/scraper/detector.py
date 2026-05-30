import difflib


class ChangeDetector:
    """Produces a human-readable unified diff between two normalized texts."""

    def unified_diff(self, old_text: str, new_text: str, label: str = "content") -> str:
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{label}:before",
            tofile=f"{label}:after",
            lineterm="",
        )
        return "\n".join(diff)
