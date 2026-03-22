# Миграция с 2KK Panel на fbtool.pro

## Контекст
2KK Panel (fbm.adway.team) больше не работает как нужно. Переходим на fbtool.pro.
Основной подход: **реверс-инжиниринг внутренних запросов** fbtool.pro, чтобы обойти лимит 100 запросов/день официального API.

## Результаты реверс-инжиниринга

### Аутентификация
- **Веб-интерфейс**: Yii2 (PHP 5.6.40, nginx), session cookie (HttpOnly), CSRF-токен (meta tag `csrf-token` + hidden input `_csrf`)
- **Логин**: `POST /login` — есть **hCaptcha**, программно не пройти
- **Решение**: пользователь логинится вручную в браузере, мы сохраняем cookies в настройках. При истечении — уведомление в Telegram
- **Cookies для auth**:
  - `_identity` — **долгоживущий** (30 дней!), содержит user_id
  - `PHPSESSID` — сессия (session-only, но обновляется автоматически при наличии _identity)
  - `_csrf` — CSRF cookie (отдельно от meta-тега CSRF)
- **CSRF-токен**: берётся из `<meta name="csrf-token">` на любой странице, нужен для всех POST-запросов
- **Официальный API**: ключ `key=API_KEY` в URL параметре (НЕ используем — лимит 100/день)

### Найденные внутренние API (веб-интерфейс)

#### Управление статусом кампаний
```
POST /task/status
Content-Type: application/x-www-form-urlencoded

action=start|stop
ids=[FB_CAMPAIGN_ID_1, FB_CAMPAIGN_ID_2, ...]   (JSON-массив строк)
account=FBTOOL_ACCOUNT_ID                         (число, напр. 18856714)
_csrf=CSRF_TOKEN
```
- `ids` — Facebook campaign IDs (НЕ internal fbtool IDs)
- `account` — fbtool internal account ID
- Ответ: 200 OK (без JSON body, просто reload)

#### Управление бюджетом
```
POST /task/budget
Content-Type: application/x-www-form-urlencoded

account=FBTOOL_ACCOUNT_ID
ad_account_id=all
objects=[FB_CAMPAIGN_ID_1, ...]                   (JSON-массив строк)
action=set|up|down                                 (set=точная сумма, up=увеличить на %, down=уменьшить на %)
param=ЗНАЧЕНИЕ                                     (число: бюджет или процент)
_csrf=CSRF_TOKEN
```

#### Управление ставкой (bid)
```
POST /task/bid
Content-Type: application/x-www-form-urlencoded

account=FBTOOL_ACCOUNT_ID
ad_account_id=all
objects=[FB_AD_ID_1, ...]
param=ЗНАЧЕНИЕ
_csrf=CSRF_TOKEN
```

#### Другие эндпоинты (не нужны для MVP)
- `POST /task/change-fp` — смена Facebook Page
- `POST /task/edit-ad` — редактирование объявления
- `POST /task/copy` — копирование
- `POST /task/rename` — переименование
- `POST /task/delete-object` — удаление
- `POST /site/copy-adset` — копирование адсета
- `POST /site/set-statistics-mode` — установить режим статистики (ads/adsets/campaigns)

### Чтение данных (SSR-страницы, парсинг HTML)

#### Статистика
```
GET /statistics?id=FBTOOL_ACCOUNT_ID&ad_account_id=all&dates=YYYY-MM-DD+-+YYYY-MM-DD&status=all&currency=USD&adaccount_status=all
```
- Режим (ads/adsets/campaigns) устанавливается через `POST /site/set-statistics-mode` (хранится в сессии)
- Таблица DataTables, колонки: Объявление, Кабинет, Аккаунт, Адсет, Показы, Клики по ссылке, CPC, Лиды, CPL, CR, CTR, CPM, Расход
- **Нам нужен режим "Кампании"** для campaign-level данных

#### Консоль (управление кампаниями)
```
GET /console?id=FBTOOL_ACCOUNT_ID&ad_account_id=all
```
- Таблица с колонками: Кампания, Бюджет, Ставка, Статус, Действия
- data-атрибуты кнопок: `data-id=FB_CAMPAIGN_ID`, `data-account=FBTOOL_ACCOUNT_ID`, `data-action=start|stop`
- `data-ad_id` на кнопках бюджета = FB campaign ID

### Официальный API (fallback, лимит 100/день)
```
GET /api/get-accounts?key=API_KEY
GET /api/get-statistics?key=API_KEY&account=ID&mode=campaigns&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&status=all
POST /api/status?key=API_KEY&account=ID    body: {id: FB_ID, action: start|stop}
```
- API key: `hRFnTofGL81mXIcNbOEGmTNElot2OtZx`
- Возвращает JSON — гораздо удобнее парсить
- get-accounts возвращает access_token для каждого аккаунта

### Маппинг ID
| Сущность | 2KK Panel | fbtool.pro |
|----------|-----------|------------|
| Аккаунт | `panel_account_id` (число) | `fbtool_account_id` (число, напр. 18856714) |
| Кампания | `internal_id` (panel ID) | `fb_campaign_id` (Facebook ID, напр. 6964648199968) |
| Рекламный кабинет | нет отдельного | `ad_account_id` (act_XXXXX) |

**Ключевое отличие от 2KK**: fbtool.pro использует **Facebook campaign ID** напрямую для всех операций, а не свой internal ID.

---

## Архитектура решения

### Выбранный подход: Полный реверс (без официального API)

Всё через внутренний веб-интерфейс — никаких лимитов.

**Чтение данных** — парсинг HTML страниц:
- `GET /statistics?id=ACCOUNT_ID&...` — статистика кампаний (spend, leads, clicks, budget, status)
- Парсим HTML-таблицу DataTables через BeautifulSoup
- Режим "Кампании" устанавливается cookie `statistics_mode=campaigns`

**Запись данных** — внутренние POST-эндпоинты:
- `POST /task/budget` — смена бюджета
- `POST /task/status` — смена статуса (start/stop)
- Нужна session cookie + CSRF-токен

**Аутентификация**:
- Cookie `_identity` живёт **30 дней** — пользователь логинится раз в месяц
- CSRF-токен берём из `<meta name="csrf-token">` при каждом GET-запросе
- При протухании cookie — уведомление в Telegram

---

## План реализации

### Шаг 1: `FbtoolClient` (замена `PanelClient`)
Новый файл `backend/app/services/fbtool_client.py`:

```python
class FbtoolClient:
    """fbtool.pro client — полный реверс-инжиниринг, без официального API."""

    def __init__(self, cookies: str):
        """cookies — строка вида '_identity=XXX; PHPSESSID=YYY; _csrf=ZZZ'"""
        self._cookies = cookies
        self._csrf_token = None  # из <meta name="csrf-token">
        self._http = httpx.AsyncClient(timeout=30)

    # === Чтение (GET + парсинг HTML) ===
    async def get_campaigns(self, account_id, date) -> list[FbtoolCampaign]:
        """Парсит /statistics?id=ACCOUNT_ID&dates=DATE+-+DATE&...
        Возвращает список кампаний со spend, leads, clicks, budget, status."""

    async def get_accounts(self) -> list[FbtoolAccount]:
        """Парсит /console — дропдаун аккаунтов."""

    # === Запись (POST, внутренний API) ===
    async def set_budget(self, account_id, fb_campaign_id, budget) -> bool:
        """POST /task/budget — action=set, param=budget"""

    async def stop_campaign(self, account_id, fb_campaign_id) -> bool:
        """POST /task/status — action=stop"""

    async def start_campaign(self, account_id, fb_campaign_id) -> bool:
        """POST /task/status — action=start"""

    # === Утилиты ===
    async def _get_page(self, url) -> str:
        """GET с cookies, возвращает HTML. Обновляет _csrf_token из мета-тега."""

    async def _post(self, url, data) -> httpx.Response:
        """POST с cookies + CSRF-токен."""

    async def _ensure_csrf(self):
        """Если нет CSRF — делает GET на / и парсит мета-тег."""
```

**Dataclasses:**
```python
@dataclass
class FbtoolCampaign:
    """Маппинг к PanelCampaign — данные из /statistics."""
    fb_campaign_id: str      # Facebook campaign ID (напр. 6963228102168)
    name: str                # Имя кампании
    daily_budget: float      # Дневной бюджет
    currency: str            # USD, EUR, etc.
    effective_status: str    # ACTIVE, PAUSED, etc.
    spend: float             # Расход за сегодня
    leads: int               # Лиды FB
    link_clicks: int         # Клики по ссылке
    impressions: int         # Показы
    fb_ad_account_id: str    # ID рекламного кабинета (act_XXX)
    account_name: str        # Имя аккаунта в fbtool
    fbtool_account_id: int   # ID аккаунта в fbtool (18856714)

@dataclass
class FbtoolAccount:
    """Маппинг к PanelAccount."""
    fbtool_id: int           # 18856714
    name: str                # КИНГ 2
    user_name: str           # Lara Nzi
```

**HTML-парсинг статистики** (BeautifulSoup):
- URL: `GET /statistics?id={account_id}&dates={date}+-+{date}&status=all&currency=USD&adaccount_status=all&ad_account_id=all`
- Cookie `statistics_mode` должен быть `campaigns`
- Таблица `#basicTable`, строки `<tr>`:
  - Ячейка 1: Кампания — имя, `(FB_CAMPAIGN_ID)`, статус (ACTIVE/PAUSED/...), бюджет `<strong>30 USD</strong>`
  - Ячейка 2: Кабинет — имя, `(FB_AD_ACCOUNT_ID)`
  - Ячейка 3: Аккаунт — `#FBTOOL_ID`, имя
  - Ячейки 4-12: Показы, Клики, CPC, Лиды, CPL, CR, CTR, CPM, Расход

**HTML-парсинг аккаунтов** (BeautifulSoup):
- URL: `GET /accounts`
- Таблица DataTable, строки `<tr>`, колонки: ID, Аккаунт, Группа, Финансы, Статус кабинета, Статус токена, Действия
- Ячейка ID: `<strong>#18856714</strong>` → fbtool_account_id
- Ячейка Аккаунт: `king 1 (100090250192918)` → имя + FB user ID
  - `Основной кабинет: Roberto Caal` → имя кабинета
  - `<strong>(877271565212706)</strong>` → FB ad account ID
- Ячейка Статус кабинета: `Активен` / пусто
- Ячейка Статус токена: `Активный` / `Ошибка`
- Ячейка Финансы: `Лимит: 50 USD/день`

### Шаг 2: Адаптация `campaign_checker.py`
- Заменить `PanelClient` → `FbtoolClient`
- Убрать `_sync_accounts_from_panel` → заменить на `fbtool.get_accounts()`
- В `_process_campaign`: использовать `fb_campaign_id` напрямую (fbtool не имеет своих internal ID для кампаний)
- Убрать `_update_account_fb_ids` — fbtool уже использует FB ID

### Шаг 3: Адаптация `action_executor.py`
- `_set_budget`: `panel.set_budget(internal_id, budget)` → `fbtool.set_budget(account_id, [fb_campaign_id], budget)`
- `_stop_campaign`: `panel.pause_campaign(internal_id)` → `fbtool.stop_campaign(account_id, [fb_campaign_id])`

### Шаг 4: Настройки пользователя
Заменить в user_settings:
- `panel_api_url` → удалить
- `panel_jwt` → `fbtool_cookies` (строка: `_identity=XXX; PHPSESSID=YYY; _csrf=ZZZ`)
- Добавить: `fbtool_account_ids` (JSON список fbtool account ID, напр. `[18856714, 18863836, 18863846, 18863966]`)

### Шаг 5: Интервал проверки
- `scheduler_service.py`: изменить интервал с 10 на 20 минут

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| `_identity` cookie истекает (30 дней) | Уведомление в Telegram за 3 дня до истечения, пользователь перелогинивается |
| hCaptcha при логине | Только ручной логин, но раз в 30 дней — приемлемо |
| Изменение верстки fbtool | HTML-парсинг через BeautifulSoup, мониторинг ошибок парсинга |
| CSRF-токен меняется | Получаем свежий из мета-тега при каждом GET-запросе |
| fbtool блокирует за частые запросы | 20-мин интервал, 4 аккаунта = ~300 запросов/день — нормально для веб-сессии |

---

## Аккаунты (найдено при реверсе)
| fbtool ID | Имя | Юзер |
|-----------|-----|------|
| 18856714 | КИНГ 2 | Lara Nzi |
| 18863836 | king 4 | Elvira Saula |
| 18863846 | king 1 | Roberto Caal |
| 18863966 | king 6 | عبدلله جغارگی |

Рекламные кабинеты (аккаунт 18856714):
- act_1941184906608238 (jyzy-BRI-terial-A)
- act_1824168095144846 (Lara Nzi)
- act_1448769840010370 (zywl-BRI-artmvstd-A)
- act_914271527780097 (jyzy-BRI-terial-B)
- act_1546770133252886 (zywl-BRI-artmvstd-C)
- act_2704943203216141 (zywl-BRI-artmvstd-B)
- act_917316584575313 (BM 728244 1)
- act_1711259669627913 (BM 728244 3)
- act_1781267622543150 (jyzy-BRI-terial-C)
- act_1645909913524789 (BM 728244 2)
