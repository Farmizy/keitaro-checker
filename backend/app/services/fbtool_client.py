"""fbtool.pro client — reverse-engineered internal web API.

No official API used (100 req/day limit). All operations via session cookies.

Auth: _identity cookie (30 days) + PHPSESSID + _csrf cookie.
Reads: GET HTML pages → parse with BeautifulSoup.
Writes: POST to /task/* endpoints with CSRF token.
"""

import re
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

    # ─── Reads (HTML parsing) ──────────────────────────────────

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_campaigns(
        self,
        account_id: int,
        date: str,
    ) -> list[FbtoolCampaign]:
        """Fetch campaign-level statistics for a given date.

        Args:
            account_id: fbtool account ID (e.g. 18856714)
            date: Date string YYYY-MM-DD
        """
        url = (
            f"{BASE_URL}/statistics"
            f"?id={account_id}"
            f"&dates={date}+-+{date}"
            f"&status=all"
            f"&currency=USD"
            f"&adaccount_status=all"
            f"&ad_account_id=all"
        )
        html = await self._get_page(url)
        return self._parse_statistics(html, account_id)

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

    # ─── HTML Parsers ──────────────────────────────────────────

    @staticmethod
    def _parse_statistics(html: str, account_id: int) -> list[FbtoolCampaign]:
        """Parse /statistics page HTML (mode=campaigns) into FbtoolCampaign list."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="basicTable")
        if not table:
            logger.warning("fbtool: statistics table #basicTable not found")
            return []

        tbody = table.find("tbody")
        if not tbody:
            return []

        campaigns = []
        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 12:
                continue

            try:
                campaign = FbtoolClient._parse_campaign_row(cells, account_id)
                if campaign:
                    campaigns.append(campaign)
            except Exception as e:
                logger.debug(f"fbtool: failed to parse stats row: {e}")
                continue

        logger.info(f"fbtool: parsed {len(campaigns)} campaigns from statistics")
        return campaigns

    @staticmethod
    def _parse_campaign_row(cells: list, account_id: int) -> FbtoolCampaign | None:
        """Parse a single <tr> from statistics table (mode=campaigns).

        Cell layout:
        0: checkbox
        1: Campaign name + (FB_ID) + STATUS + budget info
        2: Ad account (cab) name + (FB_AD_ACCOUNT_ID)
        3: Account name + #FBTOOL_ID
        4: Impressions
        5: Link clicks
        6: CPC (link)
        7: Leads
        8: CPL
        9: CR
        10: CTR (link)
        11: CPM
        12: Spend
        """
        # Cell 1: Campaign info
        camp_cell = cells[1]
        camp_text = camp_cell.get_text(" ", strip=True)

        # Extract FB campaign ID: (1234567890)
        fb_id_match = re.search(r'\((\d{10,20})\)', camp_text)
        if not fb_id_match:
            return None
        fb_campaign_id = fb_id_match.group(1)

        # Extract campaign name (everything before the FB ID)
        name = camp_text[:fb_id_match.start()].strip()

        # Extract status: look for known status strings
        status = "UNKNOWN"
        for s in ("ACTIVE", "PAUSED", "CAMPAIGN_PAUSED", "DISAPPROVED",
                   "DELETED", "ARCHIVED", "PENDING_REVIEW", "WITH_ISSUES"):
            if s in camp_text:
                status = s
                break

        # Extract budget: <strong>30 USD</strong>
        budget = 0.0
        currency = "USD"
        budget_strong = camp_cell.find("strong")
        if budget_strong:
            budget_text = budget_strong.get_text(strip=True)
            budget_match = re.match(r'([\d.]+)\s*(\w+)', budget_text)
            if budget_match:
                budget = float(budget_match.group(1))
                currency = budget_match.group(2)

        # Cell 2: Ad account
        cab_cell = cells[2]
        cab_text = cab_cell.get_text(" ", strip=True)
        fb_ad_account_id = ""
        ad_account_match = re.search(r'\((\d{10,20})\)', cab_text)
        if ad_account_match:
            fb_ad_account_id = ad_account_match.group(1)

        # Cell 3: Account
        acc_cell = cells[3]
        acc_text = acc_cell.get_text(" ", strip=True)
        # Extract account name from link
        acc_link = acc_cell.find("a")
        account_name = acc_link.get_text(strip=True) if acc_link else ""

        # Stats cells (4-12)
        def parse_num(cell_idx: int) -> float:
            text = cells[cell_idx].get_text(strip=True).replace(",", "").replace(" ", "")
            try:
                return float(text)
            except (ValueError, TypeError):
                return 0.0

        return FbtoolCampaign(
            fb_campaign_id=fb_campaign_id,
            name=name,
            daily_budget=budget,
            currency=currency,
            effective_status=status,
            impressions=int(parse_num(4)),
            link_clicks=int(parse_num(5)),
            cpc=parse_num(6),
            leads=int(parse_num(7)),
            cpl=parse_num(8),
            spend=parse_num(12),
            fb_ad_account_id=fb_ad_account_id,
            account_name=account_name,
            fbtool_account_id=account_id,
        )

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
