import pytest
from app.services.auto_launcher import (
    AutoLauncher,
    CPC_THRESHOLD_LAUNCH_1,
    CPC_THRESHOLD_LAUNCH_2,
)


DEFAULT_SETTINGS = {
    "min_roi_threshold": 0,
    "starting_budget": 30,
}


class TestClassifyCampaign:
    """Test the pure classification logic with progressive CPC thresholds."""

    # --- Proven campaigns (leads + positive ROI) always relaunch ---

    def test_proven_regardless_of_launch_count(self):
        """Has leads + positive ROI → proven, even after many launches."""
        for lc in [0, 1, 2, 5]:
            result = AutoLauncher.classify_campaign(
                leads_2d=3, roi_2d=25, launch_count=lc, cpc=0.50,
                settings=DEFAULT_SETTINGS,
            )
            assert result == "proven", f"launch_count={lc} should be proven"

    def test_proven_high_cpc_still_proven(self):
        """Proven campaign with high CPC → still proven (ROI is what matters)."""
        result = AutoLauncher.classify_campaign(
            leads_2d=2, roi_2d=50, launch_count=1, cpc=1.50,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    # --- First launch (launch_count=0): always test ---

    def test_first_launch_no_leads(self):
        """Never launched, no leads → first test."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=0, cpc=0,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_first_launch_negative_roi(self):
        """Never launched, has leads but negative ROI → still first test."""
        result = AutoLauncher.classify_campaign(
            leads_2d=1, roi_2d=-30, launch_count=0, cpc=0.60,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    # --- Second launch (launch_count=1): CPC ≤ $0.75 ---

    def test_relaunch_1_low_cpc(self):
        """Launched once, CPC=$0.50 (< $0.75) → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=1, cpc=0.50,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_relaunch_1_at_threshold(self):
        """Launched once, CPC exactly $0.75 → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=1, cpc=CPC_THRESHOLD_LAUNCH_1,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_relaunch_1_high_cpc(self):
        """Launched once, CPC=$0.80 (> $0.75) → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=1, cpc=0.80,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    # --- Third launch (launch_count=2): CPC ≤ $0.35 ---

    def test_relaunch_2_low_cpc(self):
        """Launched twice, CPC=$0.25 (< $0.35) → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=2, cpc=0.25,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_relaunch_2_at_threshold(self):
        """Launched twice, CPC exactly $0.35 → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=2, cpc=CPC_THRESHOLD_LAUNCH_2,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_relaunch_2_high_cpc(self):
        """Launched twice, CPC=$0.50 (> $0.35) → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=2, cpc=0.50,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    # --- Max launches (launch_count≥3): blacklist ---

    def test_max_launches_blacklist(self):
        """Launched 3+ times without proving → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_2d=0, roi_2d=0, launch_count=3, cpc=0.20,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    def test_max_launches_even_with_leads_negative_roi(self):
        """3+ launches, has leads but negative ROI → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_2d=2, roi_2d=-30, launch_count=3, cpc=0.20,
            settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    # --- Custom ROI threshold ---

    def test_custom_roi_threshold_below(self):
        """ROI below custom threshold → not proven, uses CPC logic."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            leads_2d=3, roi_2d=10, launch_count=1, cpc=0.50,
            settings=settings,
        )
        assert result == "new"  # CPC ok, so relaunch as new

    def test_custom_roi_threshold_above(self):
        """ROI above custom threshold → proven."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            leads_2d=3, roi_2d=25, launch_count=1, cpc=0.50,
            settings=settings,
        )
        assert result == "proven"
