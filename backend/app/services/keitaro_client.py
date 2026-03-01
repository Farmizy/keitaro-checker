"""Keitaro Internal Panel API client.

Uses session cookie auth (POST /admin/?object=auth.login).
Ref: docs/api-reference-keitaro.md
"""

from typing import Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings


class KeitaroClient:
    def __init__(
        self,
        base_url: str | None = None,
        login: str | None = None,
        password: str | None = None,
    ):
        self.base_url = (base_url or settings.keitaro_url).rstrip("/")
        self._login = login or settings.keitaro_login
        self._password = password or settings.keitaro_password
        self._session_cookie: str | None = None
        self._http = httpx.AsyncClient(timeout=30)

    async def close(self):
        await self._http.aclose()

    async def authenticate(self) -> str:
        """Login and obtain session cookie."""
        resp = await self._http.post(
            f"{self.base_url}/admin/",
            params={"object": "auth.login"},
            json={"login": self._login, "password": self._password},
        )
        resp.raise_for_status()

        session_cookie = resp.cookies.get("keitaro")
        if not session_cookie:
            # Some Keitaro versions return cookie in Set-Cookie header
            for cookie in resp.cookies.jar:
                if cookie.name == "keitaro":
                    session_cookie = cookie.value
                    break

        if not session_cookie:
            raise RuntimeError("Keitaro login failed: no session cookie returned")

        self._session_cookie = session_cookie
        logger.info("Keitaro: authenticated successfully")
        return session_cookie

    def _cookies(self) -> dict[str, str]:
        if not self._session_cookie:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return {"keitaro": self._session_cookie}

    async def _request(self, object_action: str, data: dict | None = None, method: str = "POST") -> Any:
        """Make a request to Keitaro internal API with auto re-login on 401/403."""
        kwargs: dict[str, Any] = {
            "params": {"object": object_action},
            "cookies": self._cookies(),
        }
        if data is not None:
            kwargs["json"] = data

        resp = await self._http.request(method, f"{self.base_url}/admin/", **kwargs)

        # Re-login on auth failure
        if resp.status_code in (401, 403):
            logger.warning("Keitaro: session expired, re-authenticating...")
            await self.authenticate()
            kwargs["cookies"] = self._cookies()
            resp = await self._http.request(method, f"{self.base_url}/admin/", **kwargs)

        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_conversions_by_ad(
        self,
        interval: str = "today",
        timezone: str = "Europe/Moscow",
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, int]:
        """Get conversion counts grouped by sub_id_4 (Facebook Ad ID).

        Returns:
            Dict mapping ad_id -> conversion count.
            Filters out empty ad_ids and unresolved placeholders.
        """
        body = {
            "range": {
                "interval": interval,
                "timezone": timezone,
            },
            "columns": [],
            "metrics": ["conversions"],
            "grouping": ["sub_id_4"],
            "filters": [],
            "summary": False,
            "limit": limit,
            "offset": offset,
        }

        result = await self._request("reports.build", body)
        rows = result.get("rows", [])

        ad_conversions: dict[str, int] = {}
        for row in rows:
            ad_id = row.get("sub_id_4", "")
            conversions = int(row.get("conversions", 0))

            # Skip empty, placeholder, or zero-conversion entries
            if not ad_id or ad_id == "{{ad.id}}" or conversions == 0:
                continue

            ad_conversions[ad_id] = conversions

        return ad_conversions

    async def get_all_conversions_by_ad(
        self,
        interval: str = "today",
        timezone: str = "Europe/Moscow",
    ) -> dict[str, int]:
        """Fetch all pages of conversions grouped by ad_id."""
        all_conversions: dict[str, int] = {}
        offset = 0
        limit = 500

        while True:
            batch = await self.get_conversions_by_ad(
                interval=interval,
                timezone=timezone,
                limit=limit,
                offset=offset,
            )
            if not batch:
                break
            all_conversions.update(batch)
            if len(batch) < limit:
                break
            offset += limit

        return all_conversions
