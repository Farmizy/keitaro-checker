"""2KK Panel API client (fbm.adway.team/api/).

Uses Bearer JWT auth.
Ref: docs/api-reference-2kk-panel.md
"""

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings


@dataclass
class PanelCampaign:
    """Campaign data from 2KK Panel API."""
    internal_id: int  # panel ID, used for actions
    campaign_id: str  # Facebook campaign ID
    name: str
    daily_budget: float
    effective_status: str  # ACTIVE, PAUSED, etc.
    spend: float
    spend_with_tax: float
    leads_fb: int  # FB-reported leads (we use Keitaro leads instead)
    account_name: str
    currency: str


@dataclass
class PanelAccount:
    """Account data from 2KK Panel API."""
    internal_id: int
    name: str
    status: str
    fb_account_id: str = ""


@dataclass
class PanelPage:
    """Facebook Page from 2KK Panel API."""
    id: str
    name: str


class PanelClient:
    def __init__(
        self,
        base_url: str | None = None,
        jwt_token: str | None = None,
    ):
        self.base_url = (base_url or settings.panel_api_url).rstrip("/")
        self._jwt = jwt_token or settings.panel_jwt
        self._http = httpx.AsyncClient(timeout=30)

    async def close(self):
        await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://panel.2kk.team",
            "Referer": "https://panel.2kk.team/",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_campaigns(
        self,
        start_date: str,
        end_date: str,
        page: int = 1,
        limit: int = 100,
        with_spent: bool = False,
    ) -> list[PanelCampaign]:
        """Fetch campaigns list with stats from Panel API."""
        resp = await self._http.post(
            f"{self.base_url}/campaigns",
            headers=self._headers(),
            json={
                "filter": {
                    "startDate": start_date,
                    "endDate": end_date,
                    "withSpent": with_spent,
                },
                "page": page,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"Panel API error: {data}")

        campaigns = []
        for item in data.get("data", []):
            stats = item.get("stats", {})
            cab = item.get("cab", {})
            campaigns.append(PanelCampaign(
                internal_id=item["id"],
                campaign_id=str(item.get("campaignId", "")),
                name=item.get("name", ""),
                daily_budget=float(item.get("dailyBudget") or 0),
                effective_status=item.get("effectiveStatus", "UNKNOWN"),
                spend=float(stats.get("spent", 0) or 0),
                spend_with_tax=float(stats.get("spentWithTax", 0) or 0),
                leads_fb=int(stats.get("lead", 0) or 0),
                account_name=item.get("account", {}).get("name", ""),
                currency=cab.get("currency", "USD"),
            ))

        return campaigns

    async def get_all_campaigns(
        self,
        start_date: str,
        end_date: str,
        with_spent: bool = False,
    ) -> list[PanelCampaign]:
        """Fetch all pages of campaigns."""
        all_campaigns: list[PanelCampaign] = []
        page = 1
        limit = 100

        while True:
            batch = await self.get_campaigns(
                start_date=start_date,
                end_date=end_date,
                page=page,
                limit=limit,
                with_spent=with_spent,
            )
            all_campaigns.extend(batch)
            if len(batch) < limit:
                break
            page += 1

        return all_campaigns

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_accounts(
        self,
        start_date: str,
        end_date: str,
        page: int = 1,
        limit: int = 100,
    ) -> list[PanelAccount]:
        """Fetch accounts list from Panel API."""
        resp = await self._http.post(
            f"{self.base_url}/accounts",
            headers=self._headers(),
            json={
                "filter": {
                    "startDate": start_date,
                    "endDate": end_date,
                    "withSpent": False,
                },
                "page": page,
                "limit": limit,
            },
        )
        if resp.status_code != 200:
            logger.error(f"Panel API /accounts error: status={resp.status_code} body={resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"Panel API error: {data}")

        items = data.get("data", [])
        if items:
            logger.debug(f"Panel API account keys: {list(items[0].keys())}")
            logger.debug(f"Panel API first account: {{{k}: {v} for k, v in items[0].items() if k in ('id', 'name', 'accountId', 'fbAccountId', 'account_id', 'externalId', 'cab')}}")

        return [
            PanelAccount(
                internal_id=item["id"],
                name=item.get("name", ""),
                status=item.get("status", "UNKNOWN"),
                fb_account_id=str(item.get("accountId", "")),
            )
            for item in items
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def set_budget(self, internal_id: int, daily_budget: float) -> bool:
        """Change campaign daily budget. Uses internal panel ID, not FB campaign ID."""
        resp = await self._http.post(
            f"{self.base_url}/campaigns/{internal_id}/change_budget",
            headers=self._headers(),
            json={"dailyBudget": daily_budget},
        )
        resp.raise_for_status()
        data = resp.json()
        success = data.get("success", False)

        if success:
            logger.info(f"Panel: budget set to ${daily_budget} for campaign {internal_id}")
        else:
            logger.error(f"Panel: failed to set budget for campaign {internal_id}: {data}")

        return success

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def update_campaign_status(
        self,
        campaign_ids: list[int],
        status: str,
    ) -> bool:
        """Pause or resume campaigns. Uses internal panel IDs."""
        resp = await self._http.post(
            f"{self.base_url}/campaigns/update",
            headers=self._headers(),
            json={
                "campaignsIds": campaign_ids,
                "status": status,  # "PAUSED" or "ACTIVE"
            },
        )
        resp.raise_for_status()
        logger.info(f"Panel: campaigns {campaign_ids} status -> {status}")
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry=retry_if_exception_type(httpx.HTTPStatusError))
    async def get_account_pages(self, panel_account_id: int) -> list[PanelPage]:
        """Fetch pages for a specific account from Panel API."""
        from datetime import datetime
        import zoneinfo
        today = datetime.now(zoneinfo.ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d")

        resp = await self._http.post(
            f"{self.base_url}/accounts",
            headers=self._headers(),
            json={
                "filter": {
                    "startDate": today,
                    "endDate": today,
                    "withSpent": False,
                },
                "page": 1,
                "limit": 100,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(f"Panel API error: {data}")

        for item in data.get("data", []):
            if item["id"] == panel_account_id:
                return [
                    PanelPage(id=p["id"], name=p.get("name", ""))
                    for p in item.get("pages", [])
                ]

        return []

    async def pause_campaign(self, internal_id: int) -> bool:
        return await self.update_campaign_status([internal_id], "PAUSED")

    async def resume_campaign(self, internal_id: int) -> bool:
        return await self.update_campaign_status([internal_id], "ACTIVE")
