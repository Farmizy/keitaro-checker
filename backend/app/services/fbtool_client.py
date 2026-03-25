"""fbtool.pro client — reverse-engineered internal web API.

No official API used (100 req/day limit). All operations via session cookies.

Auth: _identity cookie (30 days) + PHPSESSID + _csrf cookie.
Reads: GET /ajax/* JSON endpoints (statistics, accounts).
Writes: POST to /task/* endpoints with CSRF token.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


BASE_URL = "https://fbtool.pro"


@dataclass
class FbtoolCampaign:
    """Campaign data parsed from /statistics page (mode=campaigns)."""
    fb_campaign_id: str          # Facebook campaign ID (e.g. "6963228102168")
    name: str                    # Campaign name
    daily_budget: float          # Daily budget
    currency: str                # USD, EUR, GTQ, etc.
    effective_status: str        # ACTIVE, PAUSED, CAMPAIGN_PAUSED, etc.
    spend: float                 # Spend today
    leads: int                   # FB leads today
    link_clicks: int             # Link clicks today
    impressions: int             # Impressions today
    cpc: float = 0.0             # CPC (link)
    cpl: float = 0.0             # CPL
    fb_ad_account_id: str = ""   # FB ad account ID (e.g. "1941184906608238")
    account_name: str = ""       # Account name in fbtool (e.g. "КИНГ 2")
    fbtool_account_id: int = 0   # fbtool account ID (e.g. 18856714)


@dataclass
class FbtoolAccount:
    """Account data parsed from /accounts page."""
    fbtool_id: int               # e.g. 18856714
    name: str                    # e.g. "КИНГ 2"
    fb_user_id: str = ""         # e.g. "100004763508376"
    primary_ad_account_id: str = ""  # e.g. "1824168095144846"
    primary_ad_account_name: str = ""  # e.g. "Lara Nzi"
    cab_status: str = ""         # "Активен" or empty
    token_status: str = ""       # "Активный" or "Ошибка"
    daily_limit: str = ""        # e.g. "385.29 GTQ/день"


class FbtoolAuthError(Exception):
    """Raised when fbtool session is expired (redirected to login)."""
    pass


class FbtoolClient:
    """fbtool.pro client using reverse-engineered internal web API."""

    def __init__(self, cookies: str):
        """
        Args:
            cookies: Cookie string, e.g. '_identity=XXX; PHPSESSID=YYY; _csrf=ZZZ'
        """
        self._cookie_str = cookies
        self._csrf_token: str | None = None
        self._http = httpx.AsyncClient(
            timeout=30,
            follow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )

    async def close(self):
        await self._http.aclose()

    # ─── Reads (AJAX JSON API) ──────────────────────────────────

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_campaigns(
        self,
        account_id: int,
        date: str,
        date_from: str | None = None,
    ) -> list[FbtoolCampaign]:
        """Fetch campaign-level statistics for a date or date range via AJAX JSON API.

        Args:
            account_id: fbtool account ID (e.g. 18856714)
            date: End date string YYYY-MM-DD
            date_from: Start date string YYYY-MM-DD (defaults to date for single day)
        """
        start = date_from or date
        url = (
            f"{BASE_URL}/ajax/get-statistics"
            f"?id={account_id}"
            f"&dates={start}+-+{date}"
            f"&status=all"
            f"&currency=USD"
            f"&adaccount_status=all"
            f"&ad_account_id=all"
        )
        data = await self._get_json(url)
        return self._parse_statistics_json(data, account_id)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_accounts(self) -> list[FbtoolAccount]:
        """Fetch account list from /accounts page."""
        html = await self._get_page(f"{BASE_URL}/accounts")
        return self._parse_accounts(html)

    # ─── Writes (internal POST API) ───────────────────────────

    async def set_budget(
        self,
        account_id: int,
        fb_campaign_id: str,
        budget: float,
    ) -> bool:
        """Set exact daily budget for a campaign.

        POST /task/budget
        """
        await self._ensure_csrf()
        resp = await self._post("/task/budget", {
            "account": str(account_id),
            "ad_account_id": "all",
            "objects": f'["{fb_campaign_id}"]',
            "action": "set",
            "param": str(budget),
        })
        success = resp.status_code == 200
        if success:
            logger.info(f"fbtool: budget set to ${budget} for campaign {fb_campaign_id}")
        else:
            logger.error(f"fbtool: failed to set budget: {resp.status_code} {resp.text[:200]}")
        return success

    async def stop_campaign(
        self,
        account_id: int,
        fb_campaign_id: str,
    ) -> bool:
        """Stop (pause) a campaign.

        POST /task/status action=stop
        """
        return await self._change_status(account_id, fb_campaign_id, "stop")

    async def start_campaign(
        self,
        account_id: int,
        fb_campaign_id: str,
    ) -> bool:
        """Start (resume) a campaign.

        POST /task/status action=start
        """
        return await self._change_status(account_id, fb_campaign_id, "start")

    # ─── Internal helpers ──────────────────────────────────────

    async def _change_status(
        self, account_id: int, fb_campaign_id: str, action: str,
    ) -> bool:
        await self._ensure_csrf()
        resp = await self._post("/task/status", {
            "action": action,
            "ids": f'["{fb_campaign_id}"]',
            "account": str(account_id),
        })
        success = resp.status_code == 200
        if success:
            logger.info(f"fbtool: campaign {fb_campaign_id} → {action}")
        else:
            logger.error(f"fbtool: status change failed: {resp.status_code} {resp.text[:200]}")
        return success

    async def _get_json(self, url: str) -> Any:
        """GET a JSON endpoint with session cookies."""
        resp = await self._http.get(
            url,
            headers={
                "Cookie": self._cookie_str,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )

        if resp.status_code in (301, 302):
            location = resp.headers.get("location", "")
            if "login" in location:
                raise FbtoolAuthError("Session expired — redirected to login")

        resp.raise_for_status()
        return resp.json()

    async def _get_page(self, url: str, extra_cookies: str = "") -> str:
        """GET a page with session cookies. Returns HTML. Updates CSRF token."""
        cookies = self._cookie_str
        if extra_cookies:
            cookies = f"{cookies}; {extra_cookies}"

        resp = await self._http.get(
            url,
            headers={"Cookie": cookies},
        )

        # Check for auth redirect (302 to /login)
        if resp.status_code in (301, 302):
            location = resp.headers.get("location", "")
            if "login" in location:
                raise FbtoolAuthError("Session expired — redirected to login")

        resp.raise_for_status()
        html = resp.text

        # Extract CSRF token from meta tag
        csrf_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
        if csrf_match:
            self._csrf_token = csrf_match.group(1)

        return html

    async def _post(self, path: str, data: dict) -> httpx.Response:
        """POST to internal API with cookies + CSRF token."""
        if not self._csrf_token:
            raise FbtoolAuthError("No CSRF token available — call _ensure_csrf() first")

        data["_csrf"] = self._csrf_token

        resp = await self._http.post(
            f"{BASE_URL}{path}",
            headers={
                "Cookie": self._cookie_str,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{BASE_URL}/console",
            },
            data=data,
        )

        if resp.status_code in (301, 302):
            location = resp.headers.get("location", "")
            if "login" in location:
                raise FbtoolAuthError("Session expired — redirected to login")

        return resp

    async def _ensure_csrf(self):
        """Get a fresh CSRF token by loading the main page."""
        if not self._csrf_token:
            await self._get_page(f"{BASE_URL}/")

    # ─── JSON Parsers ───────────────────────────────────────────

    @staticmethod
    def _parse_statistics_json(data: Any, account_id: int) -> list[FbtoolCampaign]:
        """Parse /ajax/get-statistics JSON into FbtoolCampaign list.

        The JSON returns ad-level rows. We aggregate by campaign_id to get
        campaign-level spend/leads/clicks/impressions.
        Budget is in cents (campaign_daily_budget: "3000" = $30).
        """
        if not data or not isinstance(data, list):
            return []

        # Collect all rows from all groups
        all_rows: list[dict] = []
        for group in data:
            rows = group.get("rows", [])
            all_rows.extend(rows)

        if not all_rows:
            return []

        # Aggregate by campaign_id
        campaigns_map: dict[str, dict] = {}
        for row in all_rows:
            cid = row.get("campaign_id") or row.get("main_param")
            if not cid:
                continue

            if cid not in campaigns_map:
                budget_cents = int(row.get("campaign_daily_budget") or 0)
                campaigns_map[cid] = {
                    "fb_campaign_id": cid,
                    "name": row.get("campaign_name", ""),
                    "daily_budget": budget_cents / 100,
                    "currency": row.get("currency", "USD"),
                    "effective_status": row.get("campaign_effective_status", "UNKNOWN"),
                    "fb_ad_account_id": row.get("ad_account_id", ""),
                    "account_name": row.get("account_name", ""),
                    "spend": 0.0,
                    "leads": 0,
                    "link_clicks": 0,
                    "impressions": 0,
                }

            agg = campaigns_map[cid]
            agg["spend"] += float(row.get("spend") or 0)
            agg["leads"] += int(row.get("leads") or 0)
            agg["link_clicks"] += int(row.get("link_click") or 0)
            agg["impressions"] += int(row.get("impressions") or 0)

        # Build FbtoolCampaign objects
        campaigns = []
        for agg in campaigns_map.values():
            clicks = agg["link_clicks"]
            spend = agg["spend"]
            leads = agg["leads"]
            campaigns.append(FbtoolCampaign(
                fb_campaign_id=agg["fb_campaign_id"],
                name=agg["name"],
                daily_budget=agg["daily_budget"],
                currency=agg["currency"],
                effective_status=agg["effective_status"],
                spend=spend,
                leads=leads,
                link_clicks=clicks,
                impressions=agg["impressions"],
                cpc=round(spend / clicks, 2) if clicks > 0 else 0.0,
                cpl=round(spend / leads, 2) if leads > 0 else 0.0,
                fb_ad_account_id=agg["fb_ad_account_id"],
                account_name=agg["account_name"],
                fbtool_account_id=account_id,
            ))

        logger.info(f"fbtool: parsed {len(campaigns)} campaigns for account {account_id}")
        return campaigns

    @staticmethod
    def _parse_accounts(html: str) -> list[FbtoolAccount]:
        """Parse /accounts page HTML into FbtoolAccount list."""
        soup = BeautifulSoup(html, "html.parser")

        # Find the DataTable
        table = soup.find("table")
        if not table:
            logger.warning("fbtool: accounts table not found")
            return []

        tbody = table.find("tbody")
        if not tbody:
            return []

        accounts = []
        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            try:
                account = FbtoolClient._parse_account_row(cells)
                if account:
                    accounts.append(account)
            except Exception as e:
                logger.debug(f"fbtool: failed to parse account row: {e}")
                continue

        logger.info(f"fbtool: parsed {len(accounts)} accounts")
        return accounts

    @staticmethod
    def _parse_account_row(cells: list) -> FbtoolAccount | None:
        """Parse a single <tr> from /accounts table.

        Cell layout:
        0: checkbox
        1: ID (#18856714)
        2: Account (name + FB user ID + primary cab)
        3: Group
        4: Finances (limit)
        5: Cab status
        6: Token status
        7: Actions
        """
        # Cell 1: fbtool ID
        id_cell = cells[1]
        id_text = id_cell.get_text(strip=True)
        id_match = re.search(r'#(\d+)', id_text)
        if not id_match:
            return None
        fbtool_id = int(id_match.group(1))

        # Cell 2: Account info
        acc_cell = cells[2]
        acc_text = acc_cell.get_text(" ", strip=True)

        # Account name + FB user ID from first link: "КИНГ 2 (100004763508376)"
        name = ""
        fb_user_id = ""
        first_link = acc_cell.find("a")
        if first_link:
            link_text = first_link.get_text(strip=True)
            name_match = re.match(r'(.+?)\s*\((\d+)\)', link_text)
            if name_match:
                name = name_match.group(1).strip()
                fb_user_id = name_match.group(2)

        # Primary ad account: <strong> with (FB_AD_ACCOUNT_ID)
        primary_ad_account_id = ""
        primary_ad_account_name = ""
        strongs = acc_cell.find_all("strong")
        for strong in strongs:
            strong_text = strong.get_text(strip=True)
            # Check for ad account ID in parentheses
            ad_match = re.match(r'\((\d{10,20})\)', strong_text)
            if ad_match:
                primary_ad_account_id = ad_match.group(1)
            elif strong_text and not strong_text.startswith("#") and not strong_text.startswith("("):
                primary_ad_account_name = strong_text

        # Cell 4: Finances — limit
        fin_cell = cells[4]
        daily_limit = ""
        fin_text = fin_cell.get_text(" ", strip=True)
        limit_match = re.search(r'Лимит:\s*([\d.]+\s*\w+/\w+)', fin_text)
        if limit_match:
            daily_limit = limit_match.group(1)

        # Cell 5: Cab status
        cab_status = cells[5].get_text(strip=True) if len(cells) > 5 else ""

        # Cell 6: Token status
        token_status = cells[6].get_text(strip=True) if len(cells) > 6 else ""

        return FbtoolAccount(
            fbtool_id=fbtool_id,
            name=name,
            fb_user_id=fb_user_id,
            primary_ad_account_id=primary_ad_account_id,
            primary_ad_account_name=primary_ad_account_name,
            cab_status=cab_status,
            token_status=token_status,
            daily_limit=daily_limit,
        )
