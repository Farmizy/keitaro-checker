import pytest

from app.services.excel_generator import generate_fb_excel, CampaignSpec, FB_COLUMNS


def _make_spec(**overrides) -> CampaignSpec:
    defaults = dict(
        campaign_name="02.03 v1 Диабет/PL/DiabetOver(LP)/Угол v1[ral]",
        num_adsets=2,
        geo="PL",
        page_id="108126015392349",
        pixel_id="878309118145658",
        instagram_id="24862920880050484",
        daily_budget=30,
        landing_url="https://enersync-vigor.info/5BsghYCG",
        custom_audiences="giperop",
        url_tags="ad_id={{ad.id}}&fbpx=878309118145658&account_id={{account.id}}",
    )
    defaults.update(overrides)
    return CampaignSpec(**defaults)


class TestGenerateFbExcel:
    def test_single_campaign_two_adsets(self):
        """2 адсета в 1 кампании = 2 строки данных."""
        specs = [_make_spec()]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]

        # 1 header + 2 data rows
        assert ws.max_row == 3

        camp_col = headers.index("Campaign Name") + 1
        assert ws.cell(row=2, column=camp_col).value == specs[0].campaign_name
        assert ws.cell(row=3, column=camp_col).value == specs[0].campaign_name

        adset_col = headers.index("Ad Set Name") + 1
        assert ws.cell(row=2, column=adset_col).value == "New Leads Ad Set"
        assert ws.cell(row=3, column=adset_col).value == "New Leads Ad Set - Copy"

    def test_two_campaigns_two_adsets_each(self):
        """4 креатива = 2 кампании × 2 адсета = 4 строки."""
        specs = [
            _make_spec(campaign_name="02.03 v1 Test[ral]"),
            _make_spec(campaign_name="02.03 v2 Test[ral]"),
        ]
        wb = generate_fb_excel(specs)
        ws = wb.active
        assert ws.max_row == 5  # header + 4 rows

    def test_geo_in_correct_column(self):
        specs = [_make_spec(geo="BG")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        geo_col = headers.index("Countries") + 1
        assert ws.cell(row=2, column=geo_col).value == "BG"

    def test_landing_url_in_link_column(self):
        specs = [_make_spec(landing_url="https://test.com/ABC123")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        link_col = headers.index("Link") + 1
        assert ws.cell(row=2, column=link_col).value == "https://test.com/ABC123"

    def test_campaign_page_id_empty(self):
        """Campaign Page ID is empty — page set via Link Object ID."""
        specs = [_make_spec(page_id="12345")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        page_col = headers.index("Campaign Page ID") + 1
        assert ws.cell(row=2, column=page_col).value == ""

    def test_pixel_id_prefixed(self):
        specs = [_make_spec(pixel_id="99999")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        pixel_col = headers.index("Optimized Conversion Tracking Pixels") + 1
        assert ws.cell(row=2, column=pixel_col).value == "tp:99999"

    def test_instagram_id_prefixed(self):
        specs = [_make_spec(instagram_id="55555")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        ig_col = headers.index("Instagram Account ID (New)") + 1
        assert ws.cell(row=2, column=ig_col).value == "x:55555"

    def test_instagram_id_empty(self):
        specs = [_make_spec(instagram_id="")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        ig_col = headers.index("Instagram Account ID (New)") + 1
        assert ws.cell(row=2, column=ig_col).value == ""

    def test_default_language_arabic(self):
        specs = [_make_spec()]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        lang_col = headers.index("Default Language") + 1
        assert ws.cell(row=2, column=lang_col).value == "Arabic"

    def test_additional_languages_auto_filled_for_pl(self):
        specs = [_make_spec(geo="PL")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]

        lang1_col = headers.index("Additional Language 1") + 1
        lang2_col = headers.index("Additional Language 2") + 1
        lang3_col = headers.index("Additional Language 3") + 1
        lang4_col = headers.index("Additional Language 4") + 1

        assert ws.cell(row=2, column=lang1_col).value == "Albanian"
        assert ws.cell(row=2, column=lang2_col).value == "Chinese (Simplified)"
        assert ws.cell(row=2, column=lang3_col).value == "Georgian"
        assert ws.cell(row=2, column=lang4_col).value == "Polish"

    def test_additional_languages_auto_filled_for_bg(self):
        specs = [_make_spec(geo="BG")]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        lang4_col = headers.index("Additional Language 4") + 1
        assert ws.cell(row=2, column=lang4_col).value == "Bulgarian"

    def test_headers_match_fb_columns(self):
        specs = [_make_spec(num_adsets=1)]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        assert headers == FB_COLUMNS

    def test_campaign_status_paused(self):
        specs = [_make_spec(num_adsets=1)]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        status_col = headers.index("Campaign Status") + 1
        assert ws.cell(row=2, column=status_col).value == "PAUSED"

    def test_ad_names_numbered(self):
        specs = [_make_spec(num_adsets=3)]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        ad_col = headers.index("Ad Name") + 1
        assert ws.cell(row=2, column=ad_col).value == "1"
        assert ws.cell(row=3, column=ad_col).value == "2"
        assert ws.cell(row=4, column=ad_col).value == "3"

    def test_dynamic_creative_ad_format(self):
        specs = [_make_spec(num_adsets=1)]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        col = headers.index("Dynamic Creative Ad Format") + 1
        assert ws.cell(row=2, column=col).value == "Automatic Format"

    def test_no_targeting_relaxation_column(self):
        """Targeting Relaxation removed — was causing FB import errors."""
        specs = [_make_spec(num_adsets=1)]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        assert "Targeting Relaxation" not in headers

    def test_brand_safety_filtering(self):
        specs = [_make_spec(num_adsets=1)]
        wb = generate_fb_excel(specs)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        col = headers.index("Brand Safety Inventory Filtering Levels") + 1
        assert ws.cell(row=2, column=col).value == "FACEBOOK_RELAXED, AN_RELAXED"
