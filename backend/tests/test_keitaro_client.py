import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.keitaro_client import KeitaroClient


@pytest.fixture
def client():
    return KeitaroClient(
        base_url="https://test.trk.dev",
        login="testuser",
        password="testpass",
    )


def _make_cookies_mock(cookies_dict: dict):
    """Create a mock that behaves like httpx response cookies."""
    mock = MagicMock()
    mock.get = lambda k: cookies_dict.get(k)
    mock.jar = []
    return mock


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.cookies = _make_cookies_mock({"keitaro": "session123"})
        mock_resp.headers = {}

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            await client.authenticate()

        assert client._session_id == "session123"

    @pytest.mark.asyncio
    async def test_login_no_cookie_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.cookies = _make_cookies_mock({})
        mock_resp.headers = MagicMock()
        mock_resp.headers.get_list = MagicMock(return_value=[])
        mock_resp.headers.get = MagicMock(return_value="NONE")
        mock_resp.text = ""

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(RuntimeError, match="no session cookie"):
                await client.authenticate()


class TestGetConversionsByAd:
    @pytest.mark.asyncio
    async def test_parses_response(self, client):
        client._session_id = "test-session"

        api_response = {
            "rows": [
                {"sub_id_4": "120238209447230519", "conversions": 10},
                {"sub_id_4": "120240131659510277", "conversions": 5},
                {"sub_id_4": "", "conversions": 3},  # empty — skip
                {"sub_id_4": "{{ad.id}}", "conversions": 2},  # placeholder — skip
                {"sub_id_4": "120299999999999999", "conversions": 0},  # zero — skip
            ],
            "total": 5,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = api_response

        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.get_conversions_by_ad()

        assert result == {
            "120238209447230519": 10,
            "120240131659510277": 5,
        }

    @pytest.mark.asyncio
    async def test_empty_response(self, client):
        client._session_id = "test-session"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"rows": [], "total": 0}

        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.get_conversions_by_ad()

        assert result == {}

    @pytest.mark.asyncio
    async def test_relogin_on_401(self, client):
        client._session_id = "expired-session"

        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = "Unauthorized"

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.raise_for_status = MagicMock()
        resp_ok.json.return_value = {
            "rows": [{"sub_id_4": "123", "conversions": 1}],
            "total": 1,
        }

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.raise_for_status = MagicMock()
        login_resp.json.return_value = {"status": "ok"}
        login_resp.cookies = _make_cookies_mock({"keitaro": "new-session"})
        login_resp.headers = MagicMock()
        login_resp.headers.get_list = MagicMock(return_value=[])
        login_resp.headers.get = MagicMock(return_value="NONE")
        login_resp.text = ""

        with patch.object(
            client._http, "request",
            new_callable=AsyncMock,
            side_effect=[resp_401, resp_ok],
        ), patch.object(
            client._http, "post",
            new_callable=AsyncMock,
            return_value=login_resp,
        ):
            result = await client.get_conversions_by_ad()

        assert result == {"123": 1}
        assert client._session_id == "new-session"

    @pytest.mark.asyncio
    async def test_not_authenticated_raises(self, client):
        with pytest.raises(RuntimeError, match="Not authenticated"):
            await client.get_conversions_by_ad()


class TestCampaignGenerator:
    """Tests for campaign generator methods."""

    @pytest.mark.asyncio
    async def test_get_offers(self, client):
        client._session_id = "test-session"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            {"id": 1, "name": "Detoxil", "group_id": 5},
            {"id": 2, "name": "Cardiform", "group_id": 5},
        ]
        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            offers = await client.get_offers()
        assert len(offers) == 2
        assert offers[0]["name"] == "Detoxil"

    @pytest.mark.asyncio
    async def test_get_domains(self, client):
        client._session_id = "test-session"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            {"id": 1, "name": "enersync-vigor.info"},
            {"id": 2, "name": "other-domain.com"},
        ]
        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            domains = await client.get_domains()
        assert len(domains) == 2

    @pytest.mark.asyncio
    async def test_create_campaign(self, client):
        client._session_id = "test-session"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "id": 100, "alias": "V23cKdGS", "name": "test campaign",
        }
        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            campaign = await client.create_campaign(
                name="test campaign", domain="enersync-vigor.info",
            )
        assert campaign["id"] == 100
        assert campaign["alias"] == "V23cKdGS"

    @pytest.mark.asyncio
    async def test_create_stream(self, client):
        client._session_id = "test-session"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": 200, "type": "regular"}
        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            stream = await client.create_stream(
                campaign_id=100, offer_ids=[1], countries=["BG"],
            )
        assert stream["id"] == 200

    @pytest.mark.asyncio
    async def test_create_kloaka_stream(self, client):
        client._session_id = "test-session"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": 201, "name": "Kloaka"}
        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp) as mock_req:
            stream = await client.create_kloaka_stream(campaign_id=100, geo="BG")
        assert stream["id"] == 201
        # Verify the request was made with correct filters
        call_kwargs = mock_req.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["name"] == "Kloaka"
        assert body["action_payload"] == "https://google.com"


class TestGetConversionsByCampaign:
    @pytest.mark.asyncio
    async def test_parses_response(self, client):
        client._session_id = "test-session"

        api_response = {
            "rows": [
                {"sub_id_2": "120238209447240519", "conversions": 10},
                {"sub_id_2": "120240131659510277", "conversions": 5},
                {"sub_id_2": "", "conversions": 3},
                {"sub_id_2": "{{campaign_id}}", "conversions": 2},
                {"sub_id_2": "120299999999999999", "conversions": 0},
            ],
            "total": 5,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = api_response

        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.get_conversions_by_campaign()

        assert result == {
            "120238209447240519": 10,
            "120240131659510277": 5,
        }

    @pytest.mark.asyncio
    async def test_empty_response(self, client):
        client._session_id = "test-session"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"rows": [], "total": 0}

        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.get_conversions_by_campaign()

        assert result == {}


class TestGetAllConversionsByAd:
    @pytest.mark.asyncio
    async def test_pagination(self, client):
        client._session_id = "test-session"

        page1_data = {
            "rows": [
                {"sub_id_4": "ad1", "conversions": 5},
                {"sub_id_4": "ad2", "conversions": 3},
            ],
            "total": 3,
        }
        page2_data = {
            "rows": [
                {"sub_id_4": "ad3", "conversions": 1},
            ],
            "total": 3,
        }

        async def mock_request(*args, **kwargs):
            body = kwargs.get("json", {})
            offset = body.get("offset", 0)

            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = page1_data if offset == 0 else page2_data
            return resp

        with patch.object(client._http, "request", side_effect=mock_request):
            result = await client.get_conversions_by_ad(limit=2)

        assert "ad1" in result
        assert "ad2" in result
