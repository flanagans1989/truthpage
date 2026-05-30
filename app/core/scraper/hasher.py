import hashlib


class ContentHasher:
    """Produces a deterministic SHA-256 hex digest from normalized text."""

    def hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def has_changed(self, text: str, previous_hash: str) -> bool:
        return self.hash(text) != previous_hash
