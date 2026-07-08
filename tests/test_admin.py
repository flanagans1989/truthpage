from datetime import date

from app.core.config import Settings
from app.services.admin_stats import build_column_chart, build_stacked_chart


def _settings(**overrides) -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://x/x",
        JWT_SECRET="test",
        GEMINI_API_KEY="test",
        RESEND_API_KEY="test",
        _env_file=None,
        **overrides,
    )


class TestAdminEmailSet:
    def test_empty_by_default(self):
        assert _settings().admin_email_set == frozenset()

    def test_parses_and_normalizes(self):
        s = _settings(ADMIN_EMAILS=" Admin@Example.com , second@x.io ,")
        assert s.admin_email_set == {"admin@example.com", "second@x.io"}


class TestChartBuilders:
    DAYS = [date(2026, 7, d) for d in (1, 2, 3)]

    def test_column_chart_scales_to_peak(self):
        chart = build_column_chart(self.DAYS, {date(2026, 7, 1): 2, date(2026, 7, 3): 4})
        assert chart["peak"] == 4
        assert chart["total"] == 6
        assert [c["value"] for c in chart["columns"]] == [2, 0, 4]
        assert [c["pct"] for c in chart["columns"]] == [50.0, 0.0, 100.0]

    def test_column_chart_all_zero_days(self):
        chart = build_column_chart(self.DAYS, {})
        assert chart["peak"] == 1
        assert all(c["pct"] == 0.0 for c in chart["columns"])

    def test_stacked_chart_shares_one_scale(self):
        by_day = {
            date(2026, 7, 1): {"approved": 1, "rejected": 1},
            date(2026, 7, 2): {"auto_published": 4},
        }
        chart = build_stacked_chart(self.DAYS, by_day)
        assert chart["peak"] == 4
        assert chart["total"] == 6
        day1, day2, day3 = chart["columns"]
        assert day1["total"] == 2
        # zero-count statuses are dropped from segments
        assert {s["label"] for s in day1["segments"]} == {"Approved", "Rejected"}
        assert all(s["pct"] == 25.0 for s in day1["segments"])
        assert day2["segments"][0]["pct"] == 100.0
        assert day3["segments"] == []
