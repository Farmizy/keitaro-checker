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
        mock_resp.cookies = _make_cookies_mock({"keitaro": "session123"})

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.authenticate()

        assert result == "session123"
        assert client._session_cookie == "session123"

    @pytest.mark.asyncio
    async def test_login_no_cookie_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.cookies = _make_cookies_mock({})

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(RuntimeError, match="no session cookie"):
                await client.authenticate()


class TestGetConversionsByAd:
    @pytest.mark.asyncio
    async def test_parses_response(self, client):
        client._session_cookie = "test-session"

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
        client._session_cookie = "test-session"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"rows": [], "total": 0}

        with patch.object(client._http, "request", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.get_conversions_by_ad()

        assert result == {}

    @pytest.mark.asyncio
    async def test_relogin_on_401(self, client):
        client._session_cookie = "expired-session"

        resp_401 = MagicMock()
        resp_401.status_code = 401

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
        login_resp.cookies = _make_cookies_mock({"keitaro": "new-session"})

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
        assert client._session_cookie == "new-session"

    @pytest.mark.asyncio
    async def test_not_authenticated_raises(self, client):
        with pytest.raises(RuntimeError, match="Not authenticated"):
            await client.get_conversions_by_ad()


class TestGetAllConversionsByAd:
    @pytest.mark.asyncio
    async def test_pagination(self, client):
        client._session_cookie = "test-session"

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
