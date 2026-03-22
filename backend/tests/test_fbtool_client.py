import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.fbtool_client import FbtoolClient, FbtoolCampaign, FbtoolAccount, FbtoolAuthError


@pytest.fixture
def client():
    return FbtoolClient(cookies="_identity=test; PHPSESSID=test; _csrf=test")


STATISTICS_JSON = [
    {
        "info": {"base_name": "Кампания"},
        "rows": [
            {
                "id": "6963228102568",
                "account": "18856714",
                "ad_account_id": "1941184906608238",
                "campaign_id": "6963228102168",
                "campaign_name": "Test Campaign",
                "campaign_effective_status": "ACTIVE",
                "campaign_daily_budget": "3000",
                "currency": "USD",
                "spend": 15.0,
                "leads": 3,
                "link_click": 60,
                "impressions": 800,
                "account_name": "КИНГ 2",
                "main_param": "6963228102168",
            },
            {
                "id": "6963228102569",
                "account": "18856714",
                "ad_account_id": "1941184906608238",
                "campaign_id": "6963228102168",
                "campaign_name": "Test Campaign",
                "campaign_effective_status": "ACTIVE",
                "campaign_daily_budget": "3000",
                "currency": "USD",
                "spend": 15.0,
                "leads": 2,
                "link_click": 60,
                "impressions": 700,
                "account_name": "КИНГ 2",
                "main_param": "6963228102168",
            },
            {
                "id": "6964648199970",
                "account": "18856714",
                "ad_account_id": "1824168095144846",
                "campaign_id": "6964648199968",
                "campaign_name": "Paused Camp",
                "campaign_effective_status": "PAUSED",
                "campaign_daily_budget": "5000",
                "currency": "EUR",
                "spend": 0,
                "leads": 0,
                "link_click": 0,
                "impressions": 0,
                "account_name": "king 4",
                "main_param": "6964648199968",
            },
        ],
    }
]

ACCOUNTS_HTML = """
<html>
<head><meta name="csrf-token" content="csrf-abc"></head>
<body>
<table>
<thead><tr><th>Check</th><th>ID</th><th>Account</th><th>Group</th>
<th>Finances</th><th>Cab</th><th>Token</th><th>Actions</th></tr></thead>
<tbody>
<tr>
  <td><input type="checkbox"></td>
  <td><strong>#18856714</strong></td>
  <td><a href="#">КИНГ 2 (100004763508376)</a> Основной кабинет: <strong>Lara Nzi</strong> <strong>(1824168095144846)</strong></td>
  <td>Group 1</td>
  <td>Лимит: 385.29 GTQ/день</td>
  <td>Активен</td>
  <td>Активный</td>
  <td></td>
</tr>
<tr>
  <td><input type="checkbox"></td>
  <td><strong>#18863836</strong></td>
  <td><a href="#">king 4 (100090250192918)</a></td>
  <td></td>
  <td></td>
  <td></td>
  <td>Ошибка</td>
  <td></td>
</tr>
</tbody>
</table>
</body>
</html>
"""


class TestParseStatisticsJson:
    def test_parses_campaigns_aggregated(self):
        """Two ads from same campaign should be aggregated."""
        campaigns = FbtoolClient._parse_statistics_json(STATISTICS_JSON, 18856714)

        assert len(campaigns) == 2

        c1 = campaigns[0]
        assert c1.fb_campaign_id == "6963228102168"
        assert c1.name == "Test Campaign"
        assert c1.effective_status == "ACTIVE"
        assert c1.daily_budget == 30.0  # 3000 cents = $30
        assert c1.currency == "USD"
        assert c1.spend == 30.0  # 15 + 15
        assert c1.leads == 5  # 3 + 2
        assert c1.link_clicks == 120  # 60 + 60
        assert c1.impressions == 1500  # 800 + 700
        assert c1.cpc == 0.25  # 30 / 120
        assert c1.cpl == 6.0  # 30 / 5
        assert c1.fb_ad_account_id == "1941184906608238"
        assert c1.account_name == "КИНГ 2"
        assert c1.fbtool_account_id == 18856714

        c2 = campaigns[1]
        assert c2.fb_campaign_id == "6964648199968"
        assert c2.effective_status == "PAUSED"
        assert c2.daily_budget == 50.0  # 5000 cents
        assert c2.currency == "EUR"
        assert c2.spend == 0

    def test_empty_data_returns_empty(self):
        assert FbtoolClient._parse_statistics_json([], 1) == []

    def test_none_data_returns_empty(self):
        assert FbtoolClient._parse_statistics_json(None, 1) == []

    def test_empty_rows_returns_empty(self):
        assert FbtoolClient._parse_statistics_json([{"info": {}, "rows": []}], 1) == []


class TestParseAccounts:
    def test_parses_accounts(self):
        accounts = FbtoolClient._parse_accounts(ACCOUNTS_HTML)

        assert len(accounts) == 2

        a1 = accounts[0]
        assert a1.fbtool_id == 18856714
        assert a1.name == "КИНГ 2"
        assert a1.fb_user_id == "100004763508376"
        assert a1.primary_ad_account_id == "1824168095144846"
        assert a1.primary_ad_account_name == "Lara Nzi"
        assert a1.cab_status == "Активен"
        assert a1.token_status == "Активный"
        assert a1.daily_limit == "385.29 GTQ/день"

        a2 = accounts[1]
        assert a2.fbtool_id == 18863836
        assert a2.name == "king 4"
        assert a2.token_status == "Ошибка"

    def test_empty_table(self):
        html = "<html><body><table><thead></thead></table></body></html>"
        assert FbtoolClient._parse_accounts(html) == []


class TestCsrfExtraction:
    @pytest.mark.asyncio
    async def test_extracts_csrf_from_page(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><head><meta name="csrf-token" content="fresh-token"></head></html>'
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client._http, "get", new_callable=AsyncMock, return_value=mock_resp):
            html = await client._get_page("https://fbtool.pro/")

        assert client._csrf_token == "fresh-token"


class TestAuthError:
    @pytest.mark.asyncio
    async def test_redirect_to_login_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"location": "/login"}

        with patch.object(client._http, "get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(FbtoolAuthError, match="Session expired"):
                await client._get_page("https://fbtool.pro/statistics")

    @pytest.mark.asyncio
    async def test_json_redirect_to_login_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"location": "/login"}

        with patch.object(client._http, "get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(FbtoolAuthError, match="Session expired"):
                await client._get_json("https://fbtool.pro/ajax/get-statistics")


class TestSetBudget:
    @pytest.mark.asyncio
    async def test_set_budget_success(self, client):
        client._csrf_token = "test-csrf"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.set_budget(18856714, "6963228102168", 75.0)

        assert result is True
        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["account"] == "18856714"
        assert call_data["param"] == "75.0"
        assert call_data["action"] == "set"
        assert '"6963228102168"' in call_data["objects"]


class TestStopCampaign:
    @pytest.mark.asyncio
    async def test_stop_campaign_success(self, client):
        client._csrf_token = "test-csrf"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.stop_campaign(18856714, "6963228102168")

        assert result is True
        call_data = mock_post.call_args.kwargs["data"]
        assert call_data["action"] == "stop"
        assert '"6963228102168"' in call_data["ids"]
