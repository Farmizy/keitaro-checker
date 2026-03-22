import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.fbtool_client import FbtoolClient, FbtoolCampaign, FbtoolAccount, FbtoolAuthError


@pytest.fixture
def client():
    return FbtoolClient(cookies="_identity=test; PHPSESSID=test; _csrf=test")


STATISTICS_HTML = """
<html>
<head><meta name="csrf-token" content="new-csrf-token-123"></head>
<body>
<table id="basicTable">
<thead><tr><th>Check</th><th>Campaign</th><th>Cab</th><th>Account</th>
<th>Impressions</th><th>Link clicks</th><th>CPC</th><th>Leads</th>
<th>CPL</th><th>CR</th><th>CTR</th><th>CPM</th><th>Spend</th></tr></thead>
<tbody>
<tr>
  <td><input type="checkbox"></td>
  <td>Test Campaign (6963228102168) ACTIVE <strong>30 USD</strong></td>
  <td>jyzy-BRI (1941184906608238)</td>
  <td><a href="#">КИНГ 2</a> #18856714</td>
  <td>1500</td>
  <td>120</td>
  <td>0.25</td>
  <td>5</td>
  <td>6.00</td>
  <td>4.2</td>
  <td>8.0</td>
  <td>20.0</td>
  <td>30.00</td>
</tr>
<tr>
  <td><input type="checkbox"></td>
  <td>Paused Camp (6964648199968) PAUSED <strong>50 EUR</strong></td>
  <td>other-cab (1824168095144846)</td>
  <td><a href="#">king 4</a> #18863836</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
  <td>0</td>
</tr>
</tbody>
</table>
</body>
</html>
"""

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


class TestParseStatistics:
    def test_parses_campaigns(self):
        campaigns = FbtoolClient._parse_statistics(STATISTICS_HTML, 18856714)

        assert len(campaigns) == 2

        c1 = campaigns[0]
        assert c1.fb_campaign_id == "6963228102168"
        assert c1.name == "Test Campaign"
        assert c1.effective_status == "ACTIVE"
        assert c1.daily_budget == 30.0
        assert c1.currency == "USD"
        assert c1.spend == 30.0
        assert c1.leads == 5
        assert c1.link_clicks == 120
        assert c1.impressions == 1500
        assert c1.cpc == 0.25
        assert c1.cpl == 6.0
        assert c1.fb_ad_account_id == "1941184906608238"
        assert c1.account_name == "КИНГ 2"
        assert c1.fbtool_account_id == 18856714

        c2 = campaigns[1]
        assert c2.fb_campaign_id == "6964648199968"
        assert c2.effective_status == "PAUSED"
        assert c2.daily_budget == 50.0
        assert c2.currency == "EUR"
        assert c2.spend == 0

    def test_empty_table_returns_empty(self):
        html = '<html><body><table id="basicTable"><thead></thead></table></body></html>'
        assert FbtoolClient._parse_statistics(html, 1) == []

    def test_no_table_returns_empty(self):
        html = "<html><body><p>No table here</p></body></html>"
        assert FbtoolClient._parse_statistics(html, 1) == []


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
