import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.panel_client import PanelClient, PanelCampaign, PanelAccount


@pytest.fixture
def client():
    return PanelClient(
        base_url="https://test.fbm.api",
        jwt_token="test-jwt-token",
    )


CAMPAIGN_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": 48019,
            "campaignId": "120238703108910240",
            "name": "02 02 Суставы/HU/UltraVix",
            "dailyBudget": "30.00",
            "effectiveStatus": "ACTIVE",
            "account": {"name": "ph1", "status": "ACTIVE"},
            "stats": {
                "spent": 15.5,
                "spentWithTax": 15.5,
                "lead": 3,
            },
            "cab": {"name": "VH 2034", "currency": "USD"},
        },
        {
            "id": 48020,
            "campaignId": "120238703108910241",
            "name": "03 03 Похудение/PL",
            "dailyBudget": "75.00",
            "effectiveStatus": "PAUSED",
            "account": {"name": "ph2"},
            "stats": {
                "spent": 0,
                "spentWithTax": 0,
                "lead": 0,
            },
            "cab": {"currency": "USD"},
        },
    ],
    "pagination": {"total": 2},
}


class TestGetCampaigns:
    @pytest.mark.asyncio
    async def test_parses_campaigns(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = CAMPAIGN_RESPONSE

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            campaigns = await client.get_campaigns("2026-03-01", "2026-03-01")

        assert len(campaigns) == 2

        c1 = campaigns[0]
        assert c1.internal_id == 48019
        assert c1.campaign_id == "120238703108910240"
        assert c1.name == "02 02 Суставы/HU/UltraVix"
        assert c1.daily_budget == 30.0
        assert c1.effective_status == "ACTIVE"
        assert c1.spend == 15.5
        assert c1.leads_fb == 3
        assert c1.account_name == "ph1"
        assert c1.currency == "USD"

        c2 = campaigns[1]
        assert c2.internal_id == 48020
        assert c2.effective_status == "PAUSED"
        assert c2.spend == 0

    @pytest.mark.asyncio
    async def test_sends_correct_request(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": True, "data": []}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await client.get_campaigns("2026-03-01", "2026-03-01", page=2, limit=50)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "campaigns" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["filter"]["startDate"] == "2026-03-01"
        assert body["page"] == 2
        assert body["limit"] == 50

    @pytest.mark.asyncio
    async def test_api_error_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": False, "error": "Unauthorized"}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Panel API error"):
                await client.get_campaigns("2026-03-01", "2026-03-01")

    @pytest.mark.asyncio
    async def test_handles_null_stats(self, client):
        response = {
            "success": True,
            "data": [
                {
                    "id": 1,
                    "campaignId": "123",
                    "name": "Test",
                    "dailyBudget": "30.00",
                    "effectiveStatus": "ACTIVE",
                    "account": {},
                    "stats": {"spent": None, "spentWithTax": None, "lead": None},
                    "cab": {},
                },
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            campaigns = await client.get_campaigns("2026-03-01", "2026-03-01")

        assert campaigns[0].spend == 0
        assert campaigns[0].leads_fb == 0


class TestGetAccounts:
    @pytest.mark.asyncio
    async def test_parses_accounts(self, client):
        response = {
            "success": True,
            "data": [
                {"id": 2086, "name": "ph1", "status": "ACTIVE"},
                {"id": 2087, "name": "ph2", "status": "PROXY_ERROR"},
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            accounts = await client.get_accounts("2026-03-01", "2026-03-01")

        assert len(accounts) == 2
        assert accounts[0].internal_id == 2086
        assert accounts[0].name == "ph1"
        assert accounts[1].status == "PROXY_ERROR"


class TestSetBudget:
    @pytest.mark.asyncio
    async def test_set_budget_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": True}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.set_budget(48019, 75.0)

        assert result is True
        call_args = mock_post.call_args
        assert "48019/change_budget" in call_args.args[0]
        assert call_args.kwargs["json"]["dailyBudget"] == 75.0

    @pytest.mark.asyncio
    async def test_set_budget_failure(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": False, "error": "Campaign not found"}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.set_budget(99999, 75.0)

        assert result is False


class TestUpdateCampaignStatus:
    @pytest.mark.asyncio
    async def test_pause_campaign(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": True}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.pause_campaign(48019)

        assert result is True
        body = mock_post.call_args.kwargs["json"]
        assert body["campaignsIds"] == [48019]
        assert body["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_resume_campaign(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": True}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.resume_campaign(48019)

        assert result is True
        body = mock_post.call_args.kwargs["json"]
        assert body["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_batch_pause(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"success": True}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            result = await client.update_campaign_status([48019, 48020], "PAUSED")

        assert result is True
        body = mock_post.call_args.kwargs["json"]
        assert body["campaignsIds"] == [48019, 48020]


class TestHeaders:
    def test_auth_header_format(self, client):
        headers = client._headers()
        assert headers["Authorization"] == "Bearer test-jwt-token"
        assert "application/json" in headers["Content-Type"]
        assert headers["Origin"] == "https://panel.2kk.team"
