# Campaign Generator — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> **Первый шаг:** Скопировать этот файл в `docs/plans/2026-03-02-campaign-generator.md`

**Goal:** Веб-форма в существующем UI, которая генерирует Excel для bulk upload в FB Ads Manager + автоматически создаёт кампании в Keitaro.

**Architecture:** Новая страница "Campaign Generator" во фронтенде. Пользователь заполняет оффер-форму (ниша, гео, продукт, угол, кол-во кампаний и адсетов), нажимает "Generate". **Flow: Keitaro → Excel.** Сначала создаются кампании в Keitaro (internal panel API) — получаем алиас и campaign_id. Затем автоматически формируется Landing URL (`https://{domain}/{alias}`) и генерируется Excel для FB Ads Manager bulk upload.

**Tech Stack:** Python (openpyxl), FastAPI, Keitaro Internal Panel API (session cookie), React + TypeScript

---

## Конвенция именования кампаний в FB

Паттерн: `{DD.MM} v{N} {Ниша}/{Гео}/{Продукт}/{Угол} v{версия_крео}[{аккаунт}]`

Примеры:
```
25.02 v2 Диабет/PL/DiabetOver(LP)/Ewa Dąbrowska: Если уровень глюкозы v6[ral]
20.02 v1 Гипертония/LT/Cardiform/Унискауск: Если уровень давления v5 [ral]
13.02 v2 Паразиты/BG/Detoxil water/Домашний метод очищения организма v2[ral]
```

Составные части:
| Часть | Пример | Источник |
|-------|--------|----------|
| `DD.MM` | `25.02` | Сегодняшняя дата, автоматически |
| `v{N}` | `v2` | Порядковый номер кампании на оффер за день |
| `Ниша` | `Диабет` | Ввод пользователя |
| `Гео` | `PL` | Ввод пользователя (код страны) |
| `Продукт` | `DiabetOver(LP)` | Из оффера Keitaro |
| `Угол` | `Ewa Dąbrowska: ...` | Ввод пользователя (описание креатива) |
| `v{крео}` | `v6` | Версия креатива (опционально) |
| `[аккаунт]` | `[ral]` | Сокращение имени FB-аккаунта |

## Конвенция именования кампаний в Keitaro

Паттерн: `{buyer_name}/(DD.MM)/{Ниша}/{FB Account ID}/{Продукт}/{Гео}/{Домен} v{N}`

Пример:
```
raleksintsev/(02.03)/Гипер/1448769840010370/Cardiform/LT/https://enersync-vigor.info/ v2
```

| Часть | Пример | Источник |
|-------|--------|----------|
| `buyer_name` | `raleksintsev` | Имя аккаунта (полное) |
| `DD.MM` | `02.03` | Сегодняшняя дата |
| `Ниша` | `Гипер` | Сокращение ниши |
| `FB Account ID` | `1448769840010370` | `account_id` из `fb_accounts` (без `act_`) |
| `Продукт` | `Cardiform` | Из оффера |
| `Гео` | `LT` | Код страны |
| `Домен` | `https://enersync-vigor.info/` | Домен кампании |
| `v{N}` | `v2` | Порядковый номер |

## Landing URL и URL Tags

**Landing URL** генерируется автоматически:
```
https://{domain}/{keitaro_alias}
```
Пример: `https://enersync-vigor.info/V23cKdGS`

**URL Tags для FB** (ставятся в колонку "URL Tags" в Excel):
```
campaign_id={keitaro_campaign_id}&ad_id={{ad.id}}&fbpx={pixel_id}&buyer_name={buyer_name}&account_id={{account.id}}
```
- `{keitaro_campaign_id}` — ID созданной кампании Keitaro (подставляется при генерации)
- `{{ad.id}}` и `{{account.id}}` — FB dynamic parameters (остаются как есть)
- `{pixel_id}` — из профиля аккаунта
- `{buyer_name}` — имя аккаунта

## Структура кампаний

Типичный сценарий: **4 креатива на оффер** = **2 кампании × 2 адсета × 1 креатив в адсете**

В Excel для FB bulk upload каждая строка = campaign + ad set + ad. Т.е.:
- Кампания "v1" → 2 строки (ad set 1, ad set 2) — креативы добавляются вручную в FB
- Кампания "v2" → 2 строки (ad set 1, ad set 2)
- Итого 4 строки данных в Excel

---

## Keitaro — Internal Panel API

API-ключа для Admin API (`/admin_api/v1/`) нет. Используем **internal panel API** через session cookie (как существующий `keitaro_client.py`). Нужно reverse-engineer'ить endpoints для создания кампаний и потоков, а также получения списка офферов.

Известные endpoints (из `docs/api-reference-keitaro.md`):
- `POST /admin/?object=campaigns.withStats` — список кампаний
- `GET /admin/?object=campaigns.listAsOptions` — список для выбора
- `GET /admin/?object=reports.definition` — доступные метрики

Нужно исследовать:
- `POST /admin/?object=campaigns.add` — создание кампании (предположительно)
- `POST /admin/?object=streams.add` — создание потока
- `GET /admin/?object=offers.listAsOptions` или `offers.list` — список офферов

---

## Task 0: Reverse-engineer Keitaro internal API для создания кампаний

**Цель:** Через Playwright перехватить запросы при создании кампании и потока в Keitaro UI.

**Step 1:** Открыть Keitaro в браузере, открыть DevTools → Network
**Step 2:** Создать новую кампанию вручную, записать endpoint и body
**Step 3:** Создать поток для кампании, записать endpoint и body
**Step 4:** Получить список офферов, записать endpoint
**Step 5:** Задокументировать в `docs/api-reference-keitaro.md`

---

## Task 1: Расширить keitaro_client.py для создания кампаний

**Files:**
- Modify: `backend/app/services/keitaro_client.py`
- Test: `backend/tests/test_keitaro_campaign_create.py`

Добавить методы в существующий клиент (не создавать новый).

**Step 1: Написать failing тесты**

```python
# tests/test_keitaro_campaign_create.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.keitaro_client import KeitaroClient

@pytest.fixture
def client():
    return KeitaroClient(
        base_url="https://pro1.trk.dev",
        login="test",
        password="test",
    )

@pytest.mark.asyncio
async def test_get_offers(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": 1, "name": "Detoxil", "group_id": 5},
        {"id": 2, "name": "Cardiform", "group_id": 5},
    ]
    with patch.object(client, "_request", return_value=mock_response.json.return_value):
        offers = await client.get_offers()
    assert len(offers) == 2
    assert offers[0]["name"] == "Detoxil"

@pytest.mark.asyncio
async def test_create_campaign(client):
    mock_result = {"id": 100, "alias": "V23cKdGS", "name": "test campaign"}
    with patch.object(client, "_request", return_value=mock_result):
        campaign = await client.create_campaign(
            name="test campaign",
            domain="enersync-vigor.info",
        )
    assert campaign["id"] == 100

@pytest.mark.asyncio
async def test_create_stream(client):
    mock_result = {"id": 200, "type": "regular"}
    with patch.object(client, "_request", return_value=mock_result):
        stream = await client.create_stream(
            campaign_id=100,
            offer_ids=[1],
            countries=["BG"],
        )
    assert stream["id"] == 200
```

**Step 2: Запустить тесты → FAIL**

**Step 3: Добавить методы в keitaro_client.py**

```python
# Добавить в KeitaroClient:

async def _request(self, method: str, object_name: str, data: dict = None) -> dict:
    """Generic request to Keitaro internal API."""
    await self.ensure_authenticated()
    url = f"{self.base_url}/admin/"
    params = {"object": object_name}
    if method == "GET":
        resp = await self.http_client.get(url, params=params)
    else:
        resp = await self.http_client.post(url, params=params, json=data or {})
    resp.raise_for_status()
    return resp.json()

async def get_offers(self) -> list[dict]:
    """Получить список офферов."""
    return await self._request("GET", "offers.list")

async def create_campaign(self, name: str, domain: str, **kwargs) -> dict:
    """Создать кампанию в Keitaro."""
    body = {
        "name": name,
        "state": "active",
        "cost_type": "CPC",
        "cost_value": 0,
        "cost_auto": True,
        "domain": domain,
        "group_id": kwargs.get("group_id", 0),
    }
    return await self._request("POST", "campaigns.add", body)

async def get_domains(self) -> list[dict]:
    """Получить список доменов из Keitaro."""
    return await self._request("GET", "domains.list")

async def create_stream(
    self, campaign_id: int, offer_ids: list[int],
    countries: list[str], name: str = "ОСНОВНОЙ",
) -> dict:
    """Создать основной поток (ОСНОВНОЙ) с оффером."""
    body = {
        "campaign_id": campaign_id,
        "type": "regular",
        "name": name,
        "action_type": "campaign",
        "weight": 100,
        "offer_ids": offer_ids,
        "filters": [{"name": "country", "mode": "accept", "payload": countries}],
        "collect_clicks": True,
    }
    return await self._request("POST", "streams.add", body)

async def create_kloaka_stream(
    self, campaign_id: int, geo: str,
) -> dict:
    """Создать поток-клоаку (редирект на google.com, фильтр ботов + страна)."""
    body = {
        "campaign_id": campaign_id,
        "type": "regular",
        "name": "Kloaka",
        "action_type": "http",            # редирект
        "action_payload": "https://google.com",
        "weight": 0,
        "filters": [
            {"name": "bot", "mode": "accept", "payload": []},
            {"name": "country", "mode": "reject", "payload": [geo]},
            {"name": "sub_id", "mode": "reject", "payload": {
                "sub_id_name": "24242424ddda",
                "value": "fagrtgfr2211r",
            }},
        ],
        "collect_clicks": False,
    }
    return await self._request("POST", "streams.add", body)
```

> **Примечание:** Точный формат body для Kloaka нужно проверить при reverse-engineering (Task 0). Фильтры и action_type могут отличаться.

**Step 4: Тесты PASS**

**Step 5: Коммит**

```bash
git add backend/app/services/keitaro_client.py backend/tests/test_keitaro_campaign_create.py
git commit -m "feat: add campaign/stream creation to Keitaro client"
```

---

## Task 2: Таблица fb_account_profiles в Supabase

**Files:**
- Migration SQL (через Supabase MCP)

FB-аккаунты уже есть в `fb_accounts`, но нет полей Page ID / Pixel ID / Instagram ID — они нужны для генерации Excel.

**Step 1: Создать миграцию**

```sql
CREATE TABLE fb_account_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fb_account_id UUID NOT NULL REFERENCES fb_accounts(id) ON DELETE CASCADE,
    page_id TEXT NOT NULL,          -- Facebook Page ID (e.g., "108126015392349")
    pixel_id TEXT NOT NULL,         -- Pixel ID (e.g., "878309118145658")
    instagram_id TEXT DEFAULT '',   -- Instagram Account ID (e.g., "248629208800504 84")
    default_geo TEXT DEFAULT '',    -- Default country code (e.g., "BG")
    default_budget NUMERIC(10,2) DEFAULT 30,
    custom_audiences TEXT DEFAULT '',  -- e.g., "giperop"
    url_tags_template TEXT DEFAULT 'campaign_id={keitaro_campaign_id}&ad_id={{ad.id}}&fbpx={pixel_id}&buyer_name={buyer_name}&account_id={{account.id}}',
    default_language TEXT DEFAULT 'Arabic',           -- DLO default language
    additional_languages TEXT[] DEFAULT ARRAY['Albanian', 'Chinese (Simplified)', 'Georgian', 'Polish'],
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(fb_account_id)
);
```

**Step 2: Проверить создание через Supabase MCP**

---

## Task 3: Backend — CRUD для account profiles + Keitaro offers endpoint

**Files:**
- Modify: `backend/app/services/database_service.py` — CRUD для `fb_account_profiles`
- Modify: `backend/app/schemas/account.py` — добавить ProfileCreate/ProfileResponse
- Create: `backend/app/api/generator.py` — новый роутер
- Modify: `backend/app/main.py` — зарегистрировать роутер

**Step 1: Добавить схемы**

```python
# schemas/account.py — добавить
class AccountProfileCreate(BaseModel):
    fb_account_id: UUID
    page_id: str
    pixel_id: str
    instagram_id: str = ""
    default_geo: str = ""
    default_budget: float = 30
    custom_audiences: str = ""
    url_tags_template: str = "campaign_id={keitaro_campaign_id}&ad_id={{ad.id}}&fbpx={pixel_id}&buyer_name={buyer_name}&account_id={{account.id}}"

class AccountProfileResponse(BaseModel):
    id: UUID
    fb_account_id: UUID
    page_id: str
    pixel_id: str
    instagram_id: str
    default_geo: str
    default_budget: float
    custom_audiences: str
    url_tags_template: str
    created_at: datetime
    updated_at: datetime
```

**Step 2: Добавить CRUD в database_service.py**

```python
# Методы: get_account_profiles(), get_account_profile(fb_account_id),
# create_account_profile(data), update_account_profile(id, data)
```

**Step 3: Создать API-роутер generator.py**

```python
# api/generator.py
router = APIRouter(prefix="/generator", tags=["generator"])

@router.get("/offers")           # → список офферов из Keitaro
@router.get("/domains")          # → список доменов из Keitaro
@router.get("/account-profiles") # → список профилей аккаунтов с Page/Pixel IDs
@router.post("/account-profiles") # → создать/обновить профиль
@router.put("/account-profiles/{id}") # → обновить
@router.post("/generate")       # → Keitaro + Excel (единый endpoint)
```

**Step 4: Зарегистрировать в main.py**

**Step 5: Коммит**

---

## Task 4: Backend — Сервис генерации Excel

**Files:**
- Create: `backend/app/services/excel_generator.py`
- Test: `backend/tests/test_excel_generator.py`
- Modify: `backend/requirements.txt` — добавить `openpyxl`

Ключевая часть. Генерирует Excel в формате FB Ads Manager Bulk Upload. Каждая кампания может содержать несколько адсетов (по числу креативов). Каждая строка Excel = 1 campaign + 1 ad set + 1 ad (placeholder без креатива).

**Step 1: Добавить openpyxl в зависимости**

```bash
# requirements.txt — добавить
openpyxl==3.1.5
```

**Step 2: Написать failing тесты**

```python
# tests/test_excel_generator.py
from app.services.excel_generator import generate_fb_excel, CampaignSpec

def test_single_campaign_two_adsets():
    """2 адсета в 1 кампании = 2 строки данных."""
    specs = [
        CampaignSpec(
            campaign_name="02.03 v1 Диабет/PL/DiabetOver(LP)/Угол v1[ral]",
            num_adsets=2,
            geo="PL",
            page_id="108126015392349",
            pixel_id="878309118145658",
            instagram_id="24862920880050484",
            daily_budget=30,
            landing_url="https://enersync-vigor.info/5BsghYCG",
            custom_audiences="giperop",
            url_tags="ad_id={{ad.id}}&fbpx=878309118145658&account_id={{account.id}}",
        ),
    ]
    wb = generate_fb_excel(specs)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    # 1 header + 2 data rows
    assert ws.max_row == 3
    # Both rows have same campaign name
    camp_col = headers.index("Campaign Name") + 1
    assert ws.cell(row=2, column=camp_col).value == specs[0].campaign_name
    assert ws.cell(row=3, column=camp_col).value == specs[0].campaign_name
    # Ad set names differ
    adset_col = headers.index("Ad Set Name") + 1
    assert ws.cell(row=2, column=adset_col).value == "New Leads Ad Set"
    assert ws.cell(row=3, column=adset_col).value == "New Leads Ad Set - Copy"

def test_two_campaigns_two_adsets_each():
    """4 креатива = 2 кампании × 2 адсета = 4 строки данных."""
    specs = [
        CampaignSpec(
            campaign_name="02.03 v1 Диабет/PL/DiabetOver(LP)/Угол v1[ral]",
            num_adsets=2, geo="PL", page_id="1", pixel_id="2",
            instagram_id="3", daily_budget=30,
            landing_url="https://example.com", custom_audiences="", url_tags=""),
        CampaignSpec(
            campaign_name="02.03 v2 Диабет/PL/DiabetOver(LP)/Угол v1[ral]",
            num_adsets=2, geo="PL", page_id="1", pixel_id="2",
            instagram_id="3", daily_budget=30,
            landing_url="https://example.com", custom_audiences="", url_tags=""),
    ]
    wb = generate_fb_excel(specs)
    ws = wb.active
    assert ws.max_row == 5  # header + 4 data rows

def test_geo_in_correct_column():
    specs = [
        CampaignSpec(
            campaign_name="test", num_adsets=1, geo="BG",
            page_id="1", pixel_id="2", instagram_id="3",
            daily_budget=30, landing_url="https://example.com",
            custom_audiences="", url_tags=""),
    ]
    wb = generate_fb_excel(specs)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    geo_col = headers.index("Countries") + 1
    assert ws.cell(row=2, column=geo_col).value == "BG"
```

**Step 3: Реализовать генератор**

```python
# backend/app/services/excel_generator.py
from dataclasses import dataclass, field
from openpyxl import Workbook

@dataclass
class CampaignSpec:
    campaign_name: str
    num_adsets: int              # Кол-во адсетов (по 1 креативу в каждом)
    geo: str
    page_id: str
    pixel_id: str
    instagram_id: str
    daily_budget: float
    landing_url: str
    custom_audiences: str
    url_tags: str
    age_min: int = 25
    age_max: int = 65

# Ad set name suffixes для копий: "", " - Copy", " - Copy 2", ...
ADSET_SUFFIXES = ["", " - Copy", " - Copy 2", " - Copy 3", " - Copy 4"]

# Колонки FB Ads Manager Bulk Upload (порядок из CSV-экспорта пользователя)
FB_COLUMNS = [
    "Campaign Name", "Campaign Status", "Campaign Objective",
    "Buying Type", "Campaign Daily Budget", "Campaign Bid Strategy",
    "Campaign Is Using L3 Schedule", "Campaign Start Time",
    "New Objective",
    "Ad Set Run Status", "Ad Set Name", "Ad Set Time Start",
    "Destination Type", "Link Object ID",
    "Optimized Conversion Tracking Pixels", "Optimized Event",
    "Link", "Countries", "Location Types",
    "Age Min", "Age Max", "Advantage Audience", "Age Range",
    "Targeting Optimization", "Custom Audiences",
    "Targeting Relaxation",
    "Optimization Goal", "Attribution Spec", "Billing Event",
    "Ad Status", "Ad Name", "Creative Type",
    "URL Tags", "Campaign Page ID",
    "Instagram Account ID (New)",
    "Call to Action",
]

ATTRIBUTION_SPEC = '[{"event_type":"CLICK_THROUGH","window_days":1},{"event_type":"VIEW_THROUGH","window_days":1},{"event_type":"ENGAGED_VIDEO_VIEW","window_days":1}]'

def generate_fb_excel(specs: list[CampaignSpec]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Bulk Upload"

    for col, header in enumerate(FB_COLUMNS, 1):
        ws.cell(row=1, column=col, value=header)

    row_idx = 2
    for spec in specs:
        for adset_num in range(spec.num_adsets):
            suffix = ADSET_SUFFIXES[adset_num] if adset_num < len(ADSET_SUFFIXES) else f" - Copy {adset_num}"
            row_data = _build_row(spec, adset_suffix=suffix, ad_num=adset_num + 1)
            for col, header in enumerate(FB_COLUMNS, 1):
                ws.cell(row=row_idx, column=col, value=row_data.get(header, ""))
            row_idx += 1

    return wb

def _build_row(spec: CampaignSpec, adset_suffix: str, ad_num: int) -> dict:
    return {
        "Campaign Name": spec.campaign_name,
        "Campaign Status": "PAUSED",
        "Campaign Objective": "Outcome Leads",
        "Buying Type": "AUCTION",
        "Campaign Daily Budget": spec.daily_budget,
        "Campaign Bid Strategy": "Highest volume or value",
        "Campaign Is Using L3 Schedule": "Yes",
        "New Objective": "Yes",
        "Ad Set Run Status": "ACTIVE",
        "Ad Set Name": f"New Leads Ad Set{adset_suffix}",
        "Destination Type": "UNDEFINED",
        "Link Object ID": f"o:{spec.page_id}",
        "Optimized Conversion Tracking Pixels": f"tp:{spec.pixel_id}",
        "Optimized Event": "LEAD",
        "Link": spec.landing_url,
        "Countries": spec.geo,
        "Location Types": "home, recent",
        "Age Min": spec.age_min,
        "Age Max": spec.age_max,
        "Advantage Audience": 1,
        "Age Range": f"{spec.age_min}, {spec.age_max}",
        "Targeting Optimization": "expansion_all",
        "Custom Audiences": spec.custom_audiences,
        "Targeting Relaxation": "FACEBOOK_RELAXED, AN_RELAXED",
        "Optimization Goal": "OFFSITE_CONVERSIONS",
        "Attribution Spec": ATTRIBUTION_SPEC,
        "Billing Event": "IMPRESSIONS",
        "Ad Status": "ACTIVE",
        "Ad Name": f"Ad {ad_num}",
        "Creative Type": "Link Page Post Ad",
        "URL Tags": spec.url_tags,
        "Campaign Page ID": f"o:{spec.page_id}",
        "Instagram Account ID (New)": f"x:{spec.instagram_id}" if spec.instagram_id else "",
        "Call to Action": "LEARN_MORE",
    }
```

**Step 4: Тесты PASS**

```bash
cd backend && pytest tests/test_excel_generator.py -v
```

**Step 5: Коммит**

```bash
git add backend/app/services/excel_generator.py backend/tests/test_excel_generator.py backend/requirements.txt
git commit -m "feat: add FB Ads Manager Excel generator with multi-adset support"
```

---

## Task 5: Backend — API endpoint для генерации Excel + создания Keitaro кампании

**Files:**
- Modify: `backend/app/api/generator.py`
- Create: `backend/app/schemas/generator.py`
- Modify: `backend/app/main.py` — зарегистрировать роутер (keitaro_client уже инициализирован)

**Step 1: Схемы запроса**

```python
# schemas/generator.py
from pydantic import BaseModel

class CampaignEntryRequest(BaseModel):
    niche: str                        # "Диабет", "Паразиты", "Гипертония", "Суставы"
    geo: str                          # "PL", "BG", "RO", "LT"
    product_name: str                 # "DiabetOver(LP)", "Detoxil water", "Cardiform"
    angle: str                        # "Ewa Dąbrowska: Если уровень глюкозы"
    domain: str                       # "enersync-vigor.info" — домен для Keitaro
    fb_account_id: str                # UUID из нашей БД
    offer_id: int | None = None       # Keitaro offer ID (для создания потока)
    num_adsets: int = 2               # Кол-во адсетов (= креативов) в этой кампании
    daily_budget: float = 30
    creative_version: str = ""        # "v6" (опционально, в конец названия)
    # landing_url НЕ вводится — генерируется из Keitaro: https://{domain}/{alias}

class GenerateRequest(BaseModel):
    campaigns: list[CampaignEntryRequest]
```

**Step 2: Функции построения имён кампаний**

```python
# В services/campaign_name_builder.py
from datetime import datetime
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

def build_fb_campaign_name(
    entry: CampaignEntryRequest,
    campaign_number: int,
    account_short: str,
) -> str:
    """
    FB: 02.03 v1 Диабет/PL/DiabetOver(LP)/Угол v6[ral]
    """
    today = datetime.now(MOSCOW_TZ).strftime("%d.%m")
    version_suffix = f" {entry.creative_version}" if entry.creative_version else ""
    return (
        f"{today} v{campaign_number} "
        f"{entry.niche}/{entry.geo}/{entry.product_name}/"
        f"{entry.angle}{version_suffix}[{account_short}]"
    )

# Сокращения ниш для Keitaro
NICHE_SHORT = {
    "Диабет": "Диабет",
    "Гипертония": "Гипер",
    "Паразиты": "Паразиты",
    "Суставы": "Суставы",
    "Похудение": "Похуд",
}

def build_keitaro_campaign_name(
    entry: CampaignEntryRequest,
    campaign_number: int,
    buyer_name: str,
    fb_account_id: str,
) -> str:
    """
    Keitaro: raleksintsev/(02.03)/Гипер/1448769840010370/Cardiform/LT/https://enersync-vigor.info/ v2
    """
    today = datetime.now(MOSCOW_TZ).strftime("%d.%m")
    niche_short = NICHE_SHORT.get(entry.niche, entry.niche)
    # Убрать "act_" из FB account ID
    clean_account_id = fb_account_id.replace("act_", "")
    return (
        f"{buyer_name}/({today})/{niche_short}/{clean_account_id}/"
        f"{entry.product_name}/{entry.geo}/https://{entry.domain}/ v{campaign_number}"
    )
```

**Step 3: Единый endpoint — Keitaro → Excel**

Flow: Создать кампании в Keitaro → получить alias → сформировать landing URL → сгенерировать Excel.

```python
@router.post("/generate")
async def generate_campaigns(req: GenerateRequest, request: Request):
    """Создаёт кампании в Keitaro, затем генерирует Excel для FB."""
    keitaro = request.app.state.keitaro_client
    db = request.app.state.db
    specs = []
    keitaro_results = []

    for i, entry in enumerate(req.campaigns, 1):
        profile = await db.get_account_profile(entry.fb_account_id)
        account = await db.get_account(entry.fb_account_id)
        account_short = account.name[:3]

        # 1. Построить имя для Keitaro
        keitaro_name = build_keitaro_campaign_name(
            entry, i, account.name, account.account_id,
        )

        # 2. Создать кампанию в Keitaro → получить alias
        keitaro_campaign = await keitaro.create_campaign(
            name=keitaro_name, domain=entry.domain,
        )
        keitaro_id = keitaro_campaign["id"]
        alias = keitaro_campaign.get("alias", "")

        # 3. Создать потоки: Kloaka + ОСНОВНОЙ
        await keitaro.create_kloaka_stream(
            campaign_id=keitaro_id, geo=entry.geo,
        )
        if entry.offer_id:
            await keitaro.create_stream(
                campaign_id=keitaro_id,
                offer_ids=[entry.offer_id],
                countries=[entry.geo],
            )

        # 4. Сформировать landing URL
        landing_url = f"https://{entry.domain}/{alias}"

        # 5. Сформировать URL Tags (подставить реальные значения)
        url_tags = profile.url_tags_template
        url_tags = url_tags.replace("{keitaro_campaign_id}", str(keitaro_id))
        url_tags = url_tags.replace("{pixel_id}", profile.pixel_id)
        url_tags = url_tags.replace("{buyer_name}", account.name)

        # 6. Построить имя FB-кампании
        fb_name = build_fb_campaign_name(entry, i, account_short)

        specs.append(CampaignSpec(
            campaign_name=fb_name,
            num_adsets=entry.num_adsets,
            geo=entry.geo,
            page_id=profile.page_id,
            pixel_id=profile.pixel_id,
            instagram_id=profile.instagram_id,
            daily_budget=entry.daily_budget,
            landing_url=landing_url,
            custom_audiences=profile.custom_audiences,
            url_tags=url_tags,
        ))

        keitaro_results.append({
            "keitaro_id": keitaro_id,
            "alias": alias,
            "landing_url": landing_url,
            "keitaro_name": keitaro_name,
            "fb_name": fb_name,
        })

    # 7. Генерировать Excel
    wb = generate_fb_excel(specs)
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    today = datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="campaigns_{today}.xlsx"'},
    )
```

**Step 5: Использовать существующий keitaro_client (уже инициализирован в lifespan)**

Существующий `app.state.keitaro_client` уже содержит методы `create_campaign()` и `create_stream()` (добавлены в Task 1). Новый клиент не нужен.

```python
# В endpoint'ах генератора:
keitaro = request.app.state.keitaro_client
campaign = await keitaro.create_campaign(name=..., domain=...)
```

**Step 6: Коммит**

---

## Task 6: Frontend — страница Campaign Generator

**Files:**
- Create: `frontend/src/pages/GeneratorPage.tsx`
- Create: `frontend/src/api/generator.ts`
- Create: `frontend/src/hooks/useGenerator.ts`
- Modify: `frontend/src/types/index.ts` — новые типы
- Modify: `frontend/src/App.tsx` — добавить роут
- Modify: `frontend/src/components/layout/Sidebar.tsx` — добавить пункт меню

### UI-дизайн

Страница "Campaign Generator" с двумя секциями:

#### Секция 1: Таблица кампаний (основной блок)

Каждая строка = одна FB-кампания. Поля:

| Поле | Тип | Пример |
|------|-----|--------|
| Аккаунт | dropdown (из БД) | `ph1`, `ral` |
| Ниша | dropdown | `Диабет`, `Паразиты`, `Гипертония`, `Суставы` |
| Гео | input (код страны) | `PL`, `BG` |
| Продукт | input | `DiabetOver(LP)` |
| Угол | input (текст) | `Ewa Dąbrowska: Если уровень глюкозы` |
| Домен | input | `enersync-vigor.info` |
| Оффер Keitaro | dropdown (из Keitaro API) | `Detoxil [20072]` |
| Адсетов | number (1-5) | `2` |
| Бюджет | number | `30` |
| Версия крео | input | `v6` (опционально) |

> **Landing URL** не вводится — генерируется автоматически из Keitaro: `https://{domain}/{alias}`

- Кнопка "+" для добавления строки
- Кнопка "x" для удаления строки
- Автонумерация `v{N}` в названии кампании

**Предпросмотр имени** под каждой строкой:
`02.03 v1 Диабет/PL/DiabetOver(LP)/Ewa Dąbrowska: Если уровень глюкозы v6[ral]`

#### Секция 2: Настройки аккаунтов (Settings dialog)

Модалка/аккордеон для настройки FB-профилей аккаунтов:
- Page ID, Pixel ID, Instagram ID
- Custom Audiences по умолчанию
- URL Tags шаблон
- Сохраняются в БД

#### Кнопки действий

- **"Generate"** — единая кнопка: создаёт кампании в Keitaro → генерирует и скачивает xlsx
- После генерации показывает результат: список созданных кампаний Keitaro + landing URLs

**Step 1: Типы**

```typescript
// types/index.ts — добавить
export interface AccountProfile {
  id: string
  fb_account_id: string
  page_id: string
  pixel_id: string
  instagram_id: string
  default_geo: string
  default_budget: number
  custom_audiences: string
  url_tags_template: string
}

export interface KeitaroOffer {
  id: number
  name: string
  group_id: number
}

export interface CampaignFormEntry {
  niche: string
  geo: string
  product_name: string
  angle: string
  domain: string              // "enersync-vigor.info"
  fb_account_id: string
  offer_id: number | null
  num_adsets: number
  daily_budget: number
  creative_version: string
  // landing_url не вводится — генерируется из Keitaro
}
```

**Step 2: API-модуль**

```typescript
// api/generator.ts
export const getOffers = () => client.get<KeitaroOffer[]>("/generator/offers")
export const getDomains = () => client.get<string[]>("/generator/domains")
export const getProfiles = () => client.get<AccountProfile[]>("/generator/account-profiles")
export const createProfile = (data: Partial<AccountProfile>) =>
    client.post<AccountProfile>("/generator/account-profiles", data)
export const updateProfile = (id: string, data: Partial<AccountProfile>) =>
    client.put<AccountProfile>(`/generator/account-profiles/${id}`, data)
export const generateCampaigns = (campaigns: CampaignFormEntry[]) =>
    client.post("/generator/generate", { campaigns }, { responseType: "blob" })
```

**Step 3: Страница GeneratorPage.tsx**

Реализовать с react-hook-form + useFieldArray для динамических строк. Использовать существующие shadcn/ui компоненты (Button, Input, Select, Dialog, Card, Table).

**Step 4: Роутинг и навигация**

```tsx
// App.tsx — добавить роут
<Route path="/generator" element={<GeneratorPage />} />

// Sidebar.tsx — добавить пункт (иконка PlusCircle из lucide-react)
{ name: "Generator", href: "/generator", icon: PlusCircle }
```

**Step 5: Коммит**

---

## Task 7: Интеграция и тестирование

**Step 1:** Запустить backend + frontend локально
**Step 2:** Создать профиль аккаунта (ввести Page ID, Pixel ID, Instagram ID)
**Step 3:** Проверить что офферы подтягиваются из Keitaro
**Step 4:** Добавить 2-3 кампании в форму, сгенерировать Excel
**Step 5:** Открыть Excel, проверить формат колонок
**Step 6:** Загрузить Excel в FB Ads Manager (черновик), проверить что распарсился
**Step 7:** Создать кампании в Keitaro, проверить что появились в UI Keitaro
**Step 8:** Скорректировать колонки/формат если нужно

---

## Мультиязычные кампании (Dynamic Language Optimization)

Стратегия: Default Language = Arabic (catch-all), Added Languages = Albanian, Chinese (Simplified), Georgian + **язык гео кампании**. Текст одинаковый на всех языках, только на языке гео — локализованный. Видео, headline и primary text per-language добавляются вручную в FB UI.

### Маппинг гео → язык

```python
GEO_TO_LANGUAGE = {
    "PL": "Polish",
    "BG": "Bulgarian",
    "RO": "Romanian",
    "LT": "Lithuanian",
    "HU": "Hungarian",
    "CZ": "Czech",
    "HR": "Croatian",
    "SK": "Slovak",
    "SI": "Slovenian",
    "RS": "Serbian",
    "GR": "Greek",
}
BASE_LANGUAGES = ["Albanian", "Chinese (Simplified)", "Georgian"]
```

Итого additional_languages = `BASE_LANGUAGES + [GEO_TO_LANGUAGE[geo]]`

### Изменения в Excel-генераторе (Task 4)

Добавить в `CampaignSpec`:
```python
default_language: str = "Arabic"
additional_languages: list[str] = field(default_factory=list)  # автозаполняется
```

В `generate_fb_excel()` — автоматически заполнять языки:
```python
if not spec.additional_languages:
    spec.additional_languages = BASE_LANGUAGES + [GEO_TO_LANGUAGE.get(spec.geo, "")]
    spec.additional_languages = [l for l in spec.additional_languages if l]  # убрать пустые
```

Добавить колонки в `FB_COLUMNS` (после "Call to Action"):
```python
"Default Language",
"Additional Language 1",
"Additional Language 2",
"Additional Language 3",
"Additional Language 4",
```

Добавить в `_build_row()`:
```python
"Default Language": spec.default_language,
**{
    f"Additional Language {i+1}": lang
    for i, lang in enumerate(spec.additional_languages)
},
```

### Изменения во фронтенде (Task 6)

Языки выводятся автоматически по выбранному гео. Показывать **preview** под формой:
- `Languages: Arabic (default), Albanian, Chinese (Simplified), Georgian, Polish`

Опционально — редактирование набора языков через Settings.

> **Важно:** Видео, headline и primary text per-language добавляются вручную в FB UI после загрузки Excel.

---

## Verification

1. **Unit tests:**
   ```bash
   cd backend && pytest tests/test_keitaro_admin_client.py tests/test_excel_generator.py -v
   ```

2. **Manual E2E:**
   - Зайти на `/generator`, добавить кампанию
   - Скачать Excel → проверить в Excel
   - Upload в FB Ads Manager → проверить парсинг
   - Create Keitaro Campaign → проверить в Keitaro UI

3. **Edge cases:**
   - Несколько кампаний с разными аккаунтами
   - Пустые необязательные поля
   - Ошибка Keitaro API (должна показать ошибку, не крашить)
