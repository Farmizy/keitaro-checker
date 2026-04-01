from datetime import date

import pytest
from app.services.auto_launcher import (
    AutoLauncher,
    CPC_THRESHOLD_LAUNCH_1,
    CPC_THRESHOLD_LAUNCH_2,
    parse_campaign_date,
)


DEFAULT_SETTINGS = {
    "min_roi_threshold": 0,
    "starting_budget": 30,
}


class TestClassifyCampaign:
    """Test the pure classification logic with 7-day ROI + 5-day launch window."""

    # --- Proven campaigns (7-day positive ROI + leads) ---

    def test_proven_positive_roi(self):
        """7-day positive ROI + leads → proven."""
        result = AutoLauncher.classify_campaign(
            leads_7d=3, roi_7d=25, launch_count_5d=0, cpc=0.50,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    def test_proven_regardless_of_launches(self):
        """Proven even with many launches."""
        for lc in [0, 1, 2, 5]:
            result = AutoLauncher.classify_campaign(
                leads_7d=3, roi_7d=25, launch_count_5d=lc, cpc=0.50,
                last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
            )
            assert result == "proven", f"launch_count_5d={lc} should be proven"

    def test_proven_high_cpc_still_proven(self):
        """Proven campaign with high CPC → still proven (ROI matters)."""
        result = AutoLauncher.classify_campaign(
            leads_7d=2, roi_7d=50, launch_count_5d=1, cpc=1.50,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "proven"

    def test_proven_but_last_2_failed(self):
        """Positive 7-day ROI but last 2 launches failed → skip."""
        result = AutoLauncher.classify_campaign(
            leads_7d=3, roi_7d=25, launch_count_5d=2, cpc=0.30,
            last_2_launches_failed=True, settings=DEFAULT_SETTINGS,
        )
        assert result is None

    # --- CPC-based testing: 1 launch in 5 days ---

    def test_1_launch_low_cpc(self):
        """1 launch, CPC=$0.30 (< $0.50) → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=1, cpc=0.30,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_1_launch_at_threshold(self):
        """1 launch, CPC exactly $0.50 → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=1, cpc=CPC_THRESHOLD_LAUNCH_1,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_1_launch_high_cpc(self):
        """1 launch, CPC=$0.60 (> $0.50) → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=1, cpc=0.60,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    # --- CPC-based testing: 2 launches in 5 days ---

    def test_2_launches_low_cpc(self):
        """2 launches, CPC=$0.15 (< $0.25) → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=2, cpc=0.15,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_2_launches_at_threshold(self):
        """2 launches, CPC exactly $0.25 → relaunch."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=2, cpc=CPC_THRESHOLD_LAUNCH_2,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_2_launches_high_cpc(self):
        """2 launches, CPC=$0.40 (> $0.25) → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=2, cpc=0.40,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    # --- 0 launches in 5 days: first test with CPC check ---

    def test_0_launches_good_cpc(self):
        """0 launches, CPC=$0.30 (< $0.50) → first test."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=0, cpc=0.30,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"

    def test_0_launches_high_cpc(self):
        """0 launches, CPC=$0.60 (> $0.50) → skip (None, no blacklist)."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=0, cpc=0.60,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result is None

    # --- 3+ launches in 5 days → blacklist ---

    def test_3_launches_blacklist(self):
        """3+ launches without proving → blacklist."""
        result = AutoLauncher.classify_campaign(
            leads_7d=0, roi_7d=0, launch_count_5d=3, cpc=0.20,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "blacklist"

    # --- Custom ROI threshold ---

    def test_custom_roi_threshold_below(self):
        """ROI below custom threshold → not proven, uses CPC logic."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            leads_7d=3, roi_7d=10, launch_count_5d=1, cpc=0.30,
            last_2_launches_failed=False, settings=settings,
        )
        assert result == "new"

    def test_custom_roi_threshold_above(self):
        """ROI above custom threshold → proven."""
        settings = {"min_roi_threshold": 20, "starting_budget": 30}
        result = AutoLauncher.classify_campaign(
            leads_7d=3, roi_7d=25, launch_count_5d=1, cpc=0.50,
            last_2_launches_failed=False, settings=settings,
        )
        assert result == "proven"

    # --- Edge: has leads but negative ROI, 1 launch, good CPC → test ---

    def test_leads_negative_roi_1_launch_good_cpc(self):
        """Has leads but negative ROI → not proven, falls to CPC check."""
        result = AutoLauncher.classify_campaign(
            leads_7d=2, roi_7d=-30, launch_count_5d=1, cpc=0.30,
            last_2_launches_failed=False, settings=DEFAULT_SETTINGS,
        )
        assert result == "new"


class TestParseCampaignDate:
    """Test date extraction from campaign name prefix."""

    def test_standard_format(self):
        assert parse_campaign_date("30.03 v1 Диабет/ES/...", 2026) == date(2026, 3, 30)

    def test_single_digit_day(self):
        assert parse_campaign_date("3.03 v2 Суставы/PL/...", 2026) == date(2026, 3, 3)

    def test_slash_separator(self):
        assert parse_campaign_date("30/03 v1 Диабет", 2026) == date(2026, 3, 30)

    def test_no_date_prefix(self):
        assert parse_campaign_date("Promoting https://example.com", 2026) is None

    def test_invalid_date(self):
        assert parse_campaign_date("32.13 v1 Bad date", 2026) is None

    def test_with_leading_spaces(self):
        assert parse_campaign_date("  30.03 v1 Test", 2026) == date(2026, 3, 30)
