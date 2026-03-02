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
        self._http = httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/plain, */*",
            },
        )
        self._session_id: str | None = None

    async def close(self):
        await self._http.aclose()

    async def ensure_authenticated(self) -> None:
        """Authenticate only if not already authenticated."""
        if self._session_id:
            return
        await self.authenticate()

    async def authenticate(self) -> None:
        """Login and store session cookie."""
        # Clear any old cookies to get a fresh session
        self._http.cookies.clear()

        resp = await self._http.post(
            f"{self.base_url}/admin/",
            params={"object": "auth.login"},
            json={"login": self._login, "password": self._password},
        )
        resp.raise_for_status()

        body = resp.json()
        logger.debug(f"Keitaro auth response: status={resp.status_code} body_keys={list(body.keys()) if isinstance(body, dict) else 'not_dict'}")
        logger.debug(f"Keitaro auth cookies: {dict(resp.cookies)}")
        logger.debug(f"Keitaro auth Set-Cookie: {resp.headers.get('set-cookie', 'NONE')}")

        # Check if login was successful by response body
        if isinstance(body, dict) and body.get("message", "").startswith("The attempts"):
            raise RuntimeError(f"Keitaro login blocked: {body['message']}")

        # Extract session cookie
        session_id = resp.cookies.get("keitaro")

        if not session_id:
            for cookie in resp.cookies.jar:
                if cookie.name == "keitaro":
                    session_id = cookie.value
                    break

        # Parse from Set-Cookie header directly
        if not session_id:
            for header_val in resp.headers.get_list("set-cookie"):
                if "keitaro=" in header_val:
                    for part in header_val.split(";"):
                        part = part.strip()
                        if part.startswith("keitaro="):
                            session_id = part.split("=", 1)[1]
                            break
                    if session_id:
                        break

        if not session_id:
            logger.error(
                f"Keitaro: no session cookie. "
                f"status={resp.status_code} "
                f"headers={dict(resp.headers)} "
                f"body={resp.text[:500]}"
            )
            raise RuntimeError("Keitaro login failed: no session cookie returned")

        self._session_id = session_id
        logger.info(f"Keitaro: authenticated successfully (session={session_id[:8]}...)")

    async def _request(
        self,
        object_action: str,
        data: dict | None = None,
        method: str = "POST",
        extra_params: dict | None = None,
    ) -> Any:
        """Make a request to Keitaro internal API with auto re-login on 401/403."""
        if not self._session_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        params = {"object": object_action}
        if extra_params:
            params.update(extra_params)

        kwargs: dict[str, Any] = {
            "params": params,
            "cookies": {"keitaro": self._session_id},
        }
        if data is not None:
            kwargs["json"] = data

        resp = await self._http.request(method, f"{self.base_url}/admin/", **kwargs)

        logger.debug(f"Keitaro _request({object_action}): status={resp.status_code}")

        # Log response body on auth failure for debugging
        if resp.status_code in (401, 403):
            logger.warning(
                f"Keitaro: got {resp.status_code} for {object_action}, "
                f"body={resp.text[:300]}, re-authenticating..."
            )
            await self.authenticate()
            kwargs["cookies"] = {"keitaro": self._session_id}
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

    # --- Campaign Generator methods ---

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_offer_groups(self) -> list[dict]:
        """Get offer groups from Keitaro. Returns [{value: int, name: str}, ...]."""
        await self.ensure_authenticated()
        return await self._request("groups.listAsOptions", method="GET", extra_params={"type": "offers"})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_offers(self, group_id: int | None = None) -> list[dict]:
        """Get list of offers from Keitaro, optionally filtered by group."""
        await self.ensure_authenticated()
        all_offers = await self._request("offers.index", method="GET")
        if group_id is not None:
            return [o for o in all_offers if o.get("group_id") == group_id]
        return all_offers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_domains(self) -> list[dict]:
        """Get list of domains from Keitaro."""
        await self.ensure_authenticated()
        return await self._request("domains.index", method="GET")

    async def _resolve_domain_id(self, domain_name: str) -> int:
        """Resolve domain name to domain_id from Keitaro."""
        domains = await self.get_domains()
        for d in domains:
            if d.get("name") == domain_name:
                return d["id"]
        raise ValueError(f"Domain '{domain_name}' not found in Keitaro")

    # Default sub_id parameter mappings (matches existing working campaigns)
    DEFAULT_PARAMETERS = {
        "keyword": {"name": "keyword", "placeholder": "", "alias": ""},
        "cost": {"name": "cost", "placeholder": "", "alias": ""},
        "currency": {"name": "currency", "placeholder": "", "alias": ""},
        "external_id": {"name": "fbclid"},
        "creative_id": {"name": "utm_creative", "placeholder": ""},
        "ad_campaign_id": {"name": "utm_campaign", "placeholder": ""},
        "source": {"name": "utm_source", "placeholder": ""},
        "sub_id_1": {"name": "utm_placement", "placeholder": ""},
        "sub_id_2": {"name": "campaign_id", "placeholder": "{{campaign_id}}"},
        "sub_id_3": {"name": "adset_id", "placeholder": ""},
        "sub_id_4": {"name": "ad_id", "placeholder": "{{ad.id}}"},
        "sub_id_5": {"name": "adset_name", "placeholder": ""},
        "sub_id_6": {"name": "fbpx", "placeholder": "{{fbpx}}", "alias": ""},
        "sub_id_7": {"name": "buyer_name", "placeholder": "", "alias": ""},
        "sub_id_8": {"name": "account_id", "placeholder": "{{account}}", "alias": ""},
        "sub_id_11": {"name": "myTitle", "placeholder": "", "alias": ""},
        "sub_id_12": {"name": "authorName", "placeholder": "", "alias": ""},
        "sub_id_13": {"name": "imgUrl1", "placeholder": "", "alias": ""},
        "sub_id_14": {"name": "imgUrl2", "placeholder": "", "alias": ""},
        "sub_id_15": {"name": "imgUrl3", "placeholder": "", "alias": ""},
        "sub_id_30": {"name": "box", "placeholder": "", "alias": ""},
    }

    async def _resolve_campaign_group_id(self) -> int:
        """Resolve campaign group ID by login name."""
        groups = await self._request(
            "groups.listAsOptions", method="GET", extra_params={"type": "campaigns"},
        )
        for g in groups:
            if g["name"] == self._login:
                return g["value"]
        return 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def create_campaign(self, name: str, domain: str, **kwargs: Any) -> dict:
        """Create a campaign in Keitaro. Returns dict with 'id' and 'alias'."""
        import secrets
        import string
        await self.ensure_authenticated()
        domain_id = await self._resolve_domain_id(domain)
        alias = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

        # Build parameters with buyer_name placeholder
        params = dict(self.DEFAULT_PARAMETERS)
        buyer_name = kwargs.get("buyer_name", "")
        if buyer_name:
            params["sub_id_7"] = {"name": "buyer_name", "placeholder": buyer_name, "alias": ""}

        # Auto-detect campaign group
        group_id = kwargs.get("group_id") or await self._resolve_campaign_group_id()

        body = {
            "name": name,
            "alias": alias,
            "state": "active",
            "cost_type": "CPC",
            "cost_value": 0,
            "cost_auto": True,
            "type": "weight",
            "uniqueness_method": "ip_ua",
            "bind_visitors": "slo",
            "domain_id": domain_id,
            "group_id": group_id,
            "traffic_source_id": kwargs.get("traffic_source_id", 1),
            "parameters": params,
        }
        return await self._request("campaigns.create", body)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def create_stream(
        self,
        campaign_id: int,
        offer_ids: list[int],
        name: str = "ОСНОВНОЙ",
    ) -> dict:
        """Create main stream (ОСНОВНОЙ) with offer for a campaign."""
        await self.ensure_authenticated()
        body: dict[str, Any] = {
            "campaign_id": campaign_id,
            "type": "regular",
            "name": name,
            "action_type": "http",
            "action_payload": "",
            "schema": "landings",
            "weight": 100,
            "filter_or": False,
            "collect_clicks": True,
            "offer_selection": "after_click",
            "filters": [],
            "offers": [{"offer_id": oid} for oid in offer_ids],
        }
        return await self._request("streams.create", body)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def create_kloaka_stream(self, campaign_id: int, geo: str) -> dict:
        """Create cloaking stream (redirect to google.com, bot/country filters)."""
        await self.ensure_authenticated()
        body: dict[str, Any] = {
            "campaign_id": campaign_id,
            "type": "forced",
            "name": "БОТЫ И МОДЕРАЦИЯ",
            "action_type": "curl",
            "action_payload": "https://google.com",
            "schema": "redirect",
            "weight": 0,
            "filter_or": True,
            "collect_clicks": True,
            "offer_selection": "before_click",
            "filters": [
                {"name": "bot", "mode": "accept", "payload": None},
                {"name": "country", "mode": "reject", "payload": [geo]},
                {
                    "name": "parameter",
                    "mode": "reject",
                    "payload": {
                        "value": ["fagrtgfr2211r"],
                        "name": "24242424ddda",
                    },
                },
            ],
        }
        return await self._request("streams.create", body)

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
