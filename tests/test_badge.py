from app.db.models.tenant import Tenant


def _tenant(status: str, hidden: bool) -> Tenant:
    return Tenant(name="X", slug="x", subscription_status=status, hide_powered_by=hidden)


class TestBadgeVisibility:
    def test_free_plan_always_shows_the_badge(self):
        # Even if the flag was set while they were paying: the switch is a
        # paid feature, so a downgrade brings the badge back on its own.
        assert _tenant("free", hidden=True).shows_powered_by is True
        assert _tenant("free", hidden=False).shows_powered_by is True

    def test_free_plan_may_not_hide(self):
        assert _tenant("free", hidden=False).may_hide_badge is False

    def test_paid_plan_may_hide_and_the_flag_is_honoured(self):
        paid = _tenant("active", hidden=True)
        assert paid.may_hide_badge is True
        assert paid.shows_powered_by is False

    def test_paid_plan_shows_the_badge_by_default(self):
        # Default is visible; hiding is an explicit choice.
        assert _tenant("active", hidden=False).shows_powered_by is True

    def test_trial_counts_as_paid(self):
        # A trial is the Growth plan, so the white-label switch works during it.
        assert _tenant("trialing", hidden=True).shows_powered_by is False

    def test_only_the_free_plan_is_blocked(self):
        # A failed payment is a grace period, not a punishment: the switch
        # keeps working until the subscription actually ends, at which point
        # the webhook moves the tenant to "free" and the badge returns.
        for status in ("past_due", "unpaid"):
            assert _tenant(status, hidden=True).may_hide_badge is True
        assert _tenant("free", hidden=True).may_hide_badge is False

    def test_new_tenant_defaults_to_showing_the_badge(self):
        assert Tenant(name="X", slug="x").hide_powered_by in (False, None)
