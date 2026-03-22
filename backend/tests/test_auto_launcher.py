import pytest
from app.services.auto_launcher import AutoLauncher


DEFAULT_SETTINGS = {
    "min_roi_threshold": 0,
    "starting_budget": 30,
}


class TestClassifyCampaign:
    """Test the pure classification logic."""

    def test_new_campaign_no_leads(self):
        """New campaign, no leads → relaunch for testing."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, is_new=True, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_new_campaign_with_leads_positive_roi(self):
        """New campaign, has leads, positive ROI → proven."""
        result = AutoLauncher.classify_campaign(
            leads_2d=2, roi_2d=50, is_new=True, settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    def test_new_campaign_with_leads_negative_roi(self):
        """New campaign, has leads but negative ROI → still 'new' (give another chance)."""
        result = AutoLauncher.classify_campaign(
            leads_2d=1, roi_2d=-30, is_new=True, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_established_proven(self):
        """Established campaign, positive ROI, has leads → proven."""
        result = AutoLauncher.classify_campaign(
            leads_2d=3, roi_2d=25, is_new=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    def test_established_blacklist_no_leads(self):
        """Established campaign, no leads → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, is_new=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    def test_established_negative_roi_skip(self):
        """Established, has leads but negative ROI → skip (None)."""
        result = AutoLauncher.classify_campaign(
            leads_2d=2, roi_2d=-30, is_new=False, settings=DEFAULT_SETTINGS,
        )
        assert result is None

    def test_custom_roi_threshold(self):
        """ROI below custom threshold → skip."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            leads_2d=3, roi_2d=10, is_new=False, settings=settings,
        )
        assert result is None

    def test_custom_roi_threshold_proven(self):
        """ROI above custom threshold → proven."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            leads_2d=3, roi_2d=25, is_new=False, settings=settings,
        )
        assert result == "proven"
