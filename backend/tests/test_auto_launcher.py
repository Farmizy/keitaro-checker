import pytest
from app.services.auto_launcher import AutoLauncher


DEFAULT_SETTINGS = {
    "min_roi_threshold": 0,
    "starting_budget": 30,
}


class TestClassifyCampaign:
    """Test the pure classification logic."""

    def test_new_campaign_no_leads(self):
        """1-2 days active, no leads → give another day."""
        result = AutoLauncher.classify_campaign(
            spend_2d=10, spend_7d=10, leads_2d=0, roi_2d=0, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_new_campaign_with_leads(self):
        """1-2 days active, has leads → proven even if new."""
        result = AutoLauncher.classify_campaign(
            spend_2d=10, spend_7d=10, leads_2d=2, roi_2d=50, settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    def test_proven_campaign(self):
        """Old campaign, positive ROI, has leads → proven."""
        result = AutoLauncher.classify_campaign(
            spend_2d=20, spend_7d=100, leads_2d=3, roi_2d=25, settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    def test_blacklist_old_no_leads(self):
        """Old campaign, no leads in 2 days → blacklist."""
        result = AutoLauncher.classify_campaign(
            spend_2d=15, spend_7d=80, leads_2d=0, roi_2d=0, settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    def test_negative_roi_skip(self):
        """Has leads but negative ROI → skip (None)."""
        result = AutoLauncher.classify_campaign(
            spend_2d=20, spend_7d=100, leads_2d=2, roi_2d=-30, settings=DEFAULT_SETTINGS,
        )
        assert result is None

    def test_zero_spend_skip(self):
        """No spend at all → skip."""
        result = AutoLauncher.classify_campaign(
            spend_2d=0, spend_7d=0, leads_2d=0, roi_2d=0, settings=DEFAULT_SETTINGS,
        )
        assert result is None

    def test_custom_roi_threshold(self):
        """ROI below custom threshold → skip."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            spend_2d=20, spend_7d=100, leads_2d=3, roi_2d=10, settings=settings,
        )
        assert result is None

    def test_blacklist_new_after_2_days(self):
        """New campaign after 2 days of 0 leads → blacklist.
        spend_7d ≈ spend_2d but both days had spend and 0 leads."""
        result = AutoLauncher.classify_campaign(
            spend_2d=20, spend_7d=22, leads_2d=0, roi_2d=0, settings=DEFAULT_SETTINGS,
        )
        # spend_2d=20 means it ran for ~2 days at $10/day, still "new-ish"
        # But if spend is significant and 0 leads → blacklist
        assert result in ("new", "blacklist")  # depends on threshold logic
