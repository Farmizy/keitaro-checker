from unittest.mock import patch
from datetime import datetime

import zoneinfo

from app.services.campaign_name_builder import (
    build_fb_campaign_name,
    build_keitaro_campaign_name,
    MOSCOW_TZ,
)


FIXED_NOW = datetime(2026, 3, 2, 12, 0, 0, tzinfo=MOSCOW_TZ)


@patch("app.services.campaign_name_builder.datetime")
class TestBuildFbCampaignName:
    def test_basic(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = build_fb_campaign_name(
            niche="Диабет",
            geo="PL",
            product_name="DiabetOver(LP)",
            angle="Ewa Dąbrowska: Если уровень глюкозы",
            campaign_number=1,
            account_short="ral",
            creative_version="v6",
        )
        assert result == (
            "02.03 v1 Диабет/PL/DiabetOver(LP)/"
            "Ewa Dąbrowska: Если уровень глюкозы v6[ral]"
        )

    def test_no_creative_version(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = build_fb_campaign_name(
            niche="Паразиты",
            geo="BG",
            product_name="Detoxil",
            angle="Домашний метод",
            campaign_number=2,
            account_short="ph1",
        )
        assert result == "02.03 v2 Паразиты/BG/Detoxil/Домашний метод[ph1]"


@patch("app.services.campaign_name_builder.datetime")
class TestBuildKeitaroCampaignName:
    def test_basic(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = build_keitaro_campaign_name(
            niche="Гипертония",
            geo="LT",
            product_name="Cardiform",
            domain="enersync-vigor.info",
            campaign_number=2,
            buyer_name="raleksintsev",
            fb_account_id="act_1448769840010370",
        )
        assert result == (
            "raleksintsev/(02.03)/Гипер/1448769840010370/"
            "Cardiform/LT/https://enersync-vigor.info/ v2"
        )

    def test_strips_act_prefix(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = build_keitaro_campaign_name(
            niche="Диабет",
            geo="PL",
            product_name="DiabetOver",
            domain="test.com",
            campaign_number=1,
            buyer_name="buyer",
            fb_account_id="act_12345",
        )
        assert "act_" not in result
        assert "/12345/" in result

    def test_unknown_niche_keeps_full_name(self, mock_dt):
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        result = build_keitaro_campaign_name(
            niche="Зрение",
            geo="RO",
            product_name="EyeMax",
            domain="x.com",
            campaign_number=1,
            buyer_name="test",
            fb_account_id="999",
        )
        assert "/Зрение/" in result
