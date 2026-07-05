from app.core.scraper.detector import ChangeDetector
from app.core.scraper.hasher import ContentHasher

_h = ContentHasher()
_d = ChangeDetector()


def test_hash_is_deterministic():
    assert _h.hash("abc") == _h.hash("abc")
    assert _h.hash("abc") != _h.hash("abd")
    assert len(_h.hash("abc")) == 64


def test_has_changed():
    h = _h.hash("same")
    assert _h.has_changed("different", h) is True
    assert _h.has_changed("same", h) is False


def test_unified_diff_contains_change_markers():
    diff = _d.unified_diff("old line", "new line", label="https://x.com/privacy")
    assert "-old line" in diff
    assert "+new line" in diff
    assert "https://x.com/privacy:before" in diff


def test_unified_diff_identical_is_empty():
    assert _d.unified_diff("same", "same") == ""
