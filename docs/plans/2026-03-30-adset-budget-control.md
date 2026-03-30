# Контроль бюджетов на уровне адсетов (ABO-кампании)

## Контекст

Сейчас система работает только с CBO-кампаниями (budget_level=campaign). При ABO (Adset Budget Optimization) бюджет задаётся на уровне каждого адсета, а campaign_daily_budget = 0. Система такие кампании видит, но не может ими управлять — бюджет 0, повышать некуда.

Нужно: определять ABO-кампании, разбивать их на адсеты, применять лестницу правил к каждому адсету отдельно.

## Ключевое решение: адсет = строка в `campaigns`

Не создаём отдельную таблицу `adsets`. Для ABO-кампании в таблице `campaigns` появляется **по одной строке на адсет** с `budget_level=adset` и заполненным `fb_adset_id`. Это минимизирует изменения — rule_engine, action_executor, frontend, API работают с той же таблицей.

**Модель уже готова**: `Campaign` имеет поля `fb_adset_id` и `budget_level` (CAMPAIGN|ADSET).

## Результаты проверки fbtool JSON (2026-03-30)

**1. Adset-поля есть в JSON** — `/ajax/get-statistics` возвращает 62 поля на строку, включая:
- `adset_id` — Facebook adset ID (e.g. `"6963228102368"`)
- `adset_name` — имя адсета (e.g. `"New Leads Ad Set"`)
- `adset_daily_budget` — бюджет в центах (`"0"` для CBO, `"1000"` = $10 для ABO)
- `adset_effective_status` — статус адсета
- `adset_status` — базовый статус
- `adset_lifetime_budget` — lifetime бюджет

Отдельный запрос `set-statistics-mode` **не нужен** — все данные в одном JSON.

**2. CBO vs ABO определение:** `campaign_daily_budget > 0` → CBO, `campaign_daily_budget == 0` и `adset_daily_budget > 0` → ABO.

**3. set_budget / stop с adset ID** — не проверено (нет активных ABO-кампаний). В HTML fbtool использует формат `{account_id}_{adset_id}` для действий с адсетами. Нужно проверить при первой ABO-кампании.

## Лестница правил для адсетов

Стопы — те же что для CBO. Повышение бюджета зависит от начального бюджета адсета:

### Стопы (одинаковые для CBO и ABO)
| Spend | Лиды | Действие |
|-------|------|----------|
| >= $2.50, CPC > $0.45 | 0 | STOP (ранний CPC) |
| >= $7 | 0 | STOP |
| >= $15 | 1 | STOP |
| >= $23 | 2 | STOP |
| >= $31 | 3 | STOP |
| >= $39 | 4 | STOP |
| >= $47, CPL > $10 | 5+ | STOP |

### Повышение бюджета (отличается от CBO)

**Если текущий бюджет ≤ $20** (маленький старт, $10-$20):
| Лиды | Действие |
|------|----------|
| 1 | Бюджет → $20 |
| 3 | Бюджет → $75 |
| 4 | Бюджет → $150 |
| 6 | Бюджет → $250 |

**Если текущий бюджет > $20** ($21-$25):
| Лиды | Действие |
|------|----------|
| 2 | Бюджет → $75 |
| 4 | Бюджет → $150 |
| 6 | Бюджет → $250 |

### Реализация в rule_engine

Rule engine не меняется. Набор `budget_steps` выбирается **перед** вызовом `evaluate()` в campaign_checker:

```python
# В _process_adset():
if current_budget <= 20:
    budget_steps = [(6, 250), (4, 150), (3, 75), (1, 20)]
else:
    budget_steps = [(6, 250), (4, 150), (2, 75)]

action = evaluate(state, now, budget_steps=budget_steps, **rule_kwargs)
```

Это работает потому что `evaluate()` проверяет `state.leads >= min_leads AND state.current_budget < target_budget`:
- Бюджет $10, 1 лид → $10 < $20 → SET $20 ✓
- Бюджет $20, 2 лида → нет шага для 2 лидов (нужно 3) → WAIT ✓
- Бюджет $20, 3 лида → $20 < $75 → SET $75 ✓
- Бюджет $25, 1 лид → $25 ≥ $20, нет шага → WAIT ✓
- Бюджет $25, 2 лида → $25 < $75 → SET $75 ✓

## Изменения по слоям

### 1. fbtool_client.py

**Новый dataclass:**
```python
@dataclass
class FbtoolAdset:
    fb_adset_id: str              # Facebook adset ID
    fb_campaign_id: str           # Родительская кампания
    name: str                     # Имя адсета
    campaign_name: str            # Имя кампании
    daily_budget: float           # Бюджет адсета
    currency: str
    effective_status: str         # Статус адсета
    spend: float
    leads: int
    link_clicks: int
    impressions: int
    cpc: float = 0.0
    cpl: float = 0.0
    fb_ad_account_id: str = ""
    account_name: str = ""
    fbtool_account_id: int = 0
```

**Изменения в `_parse_statistics_json`:**

Текущий парсер агрегирует ad-level строки по `campaign_id`. Нужно:
- Извлекать `adset_id`, `adset_daily_budget` из каждой строки
- Определять тип бюджета: если `campaign_daily_budget > 0` → CBO, иначе ABO
- Для CBO — оставить текущую агрегацию по campaign_id (без изменений)
- Для ABO — агрегировать по `adset_id`, создавать `FbtoolAdset`

**Новый метод или расширение `get_campaigns()`:**
```python
async def get_campaigns(self, account_id, date, date_from=None) -> tuple[list[FbtoolCampaign], list[FbtoolAdset]]:
    """Возвращает CBO-кампании и ABO-адсеты."""
```

Или отдельный метод `get_adsets()` — зависит от того, нужен ли отдельный запрос (другой `statistics-mode`) или adset-данные уже есть в том же JSON.

**Действия с адсетами** — `set_budget` и `stop_campaign`/`start_campaign` должны работать с adset ID:
```python
async def set_budget(self, account_id, object_id, budget):
    """object_id = fb_campaign_id или fb_adset_id"""
    # objects=["{object_id}"] — fbtool передаёт в FB API напрямую
```

Текущая сигнатура уже принимает `fb_campaign_id: str` — достаточно переименовать в `object_id` или передавать adset_id в тот же параметр. Facebook API различает campaign и adset по ID автоматически.

### 2. keitaro_client.py

**Новый метод для лидов по адсету:**
```python
async def get_conversions_by_adset(
    self, interval="today", timezone="Europe/Moscow", limit=500, offset=0,
) -> dict[str, int]:
    """Конверсии по sub_id_3 (adset_id). Возвращает {adset_id: count}."""
```

Аналогичен `get_conversions_by_campaign()`, но `grouping: ["sub_id_3"]`.

**Требование к трекинг-ссылке FB**: в URL-параметрах рекламы должен быть `adset_id={{adset.id}}`, который передаётся в Keitaro через sub_id_3. Сейчас placeholder пустой — нужно обновить в настройках FB-рекламы.

Пагинация — аналогичный метод `get_all_conversions_by_adset()`.

### 3. campaign_checker.py

**Определение CBO vs ABO:**
При парсинге fbtool-данных — если `campaign_daily_budget == 0` и есть адсеты с `adset_daily_budget > 0` → ABO.

**Обработка ABO:**
```python
# Текущий flow (CBO):
for fc in all_fbtool_campaigns:
    self._process_campaign(fc, ...)

# Новый flow:
for fc in all_fbtool_campaigns:
    self._process_campaign(fc, ...)   # CBO — как раньше

for adset in all_fbtool_adsets:
    self._process_adset(adset, ...)   # ABO — новый метод
```

**`_process_adset`** — аналогичен `_process_campaign`, но:
- Синхронизирует в DB как строку с `budget_level=adset`, `fb_adset_id=adset.fb_adset_id`
- Берёт лиды из `keitaro_adset_conversions[adset_id]` (sub_id_3)
- Передаёт в rule_engine тот же `CampaignState` (engine'у всё равно — он работает с spend/leads/budget)
- При выполнении действия — передаёт `fb_adset_id` в action_executor

**`_sync_adset`** — новый метод, аналог `_sync_campaign`:
- Upsert по `fb_account_id + fb_adset_id` (вместо fb_campaign_id)
- Сохраняет `fb_campaign_id` как parent reference
- `budget_level = "adset"`

### 4. action_executor.py

Минимальные изменения. Нужно передавать правильный `object_id` в fbtool:

```python
async def execute(self, action, campaign_db_id, fb_object_id, fbtool_account_id, fb_account_id):
    """fb_object_id = fb_campaign_id (CBO) или fb_adset_id (ABO)."""
```

Или добавить параметр `budget_level` и выбирать ID:
```python
async def execute(self, ..., fb_campaign_id, fb_adset_id=None, budget_level="campaign"):
    object_id = fb_adset_id if budget_level == "adset" else fb_campaign_id
```

### 5. rule_engine.py

**Без изменений в core-логике.** `evaluate()` работает с абстрактным `CampaignState` — ему без разницы, кампания это или адсет.

**Возможно**: отдельные пороги для адсетов (адсеты обычно тратят меньше кампаний). Это можно сделать через отдельный `rule_set` в DB с `budget_level=adset`. Но на первом этапе — те же пороги.

### 6. database_service.py

**Новые методы:**
```python
def get_campaign_by_adset_id(self, fb_account_id, fb_adset_id) -> dict | None:
    """Найти запись по fb_adset_id."""

def upsert_adset(self, data: dict) -> dict:
    """Upsert по fb_account_id + fb_adset_id."""
```

**Индексы:**
- Добавить индекс на `(fb_account_id, fb_adset_id)` WHERE `fb_adset_id IS NOT NULL`

### 7. DB миграция

```sql
-- 007_adset_support.sql

-- Индекс для быстрого поиска адсетов
CREATE INDEX IF NOT EXISTS idx_campaigns_adset
ON campaigns (fb_account_id, fb_adset_id)
WHERE fb_adset_id IS NOT NULL;

-- Дефолт для budget_level
ALTER TABLE campaigns
ALTER COLUMN budget_level SET DEFAULT 'campaign';
```

Новых колонок не нужно — `fb_adset_id` и `budget_level` уже есть в модели и таблице.

### 8. Frontend

**CampaignsPage:**
- Отображать колонку "Тип" (CBO/ABO) или иконку
- Для ABO-адсетов показывать имя родительской кампании
- Группировка: кампания → её адсеты (collapsible)

**Фильтрация:**
- Добавить фильтр по `budget_level` (все / CBO / ABO)

**LogsPage:**
- В логах действий показывать, к чему применено (кампания или адсет)

### 9. Auto-launcher

На первом этапе — только CBO. Авто-лаунчер для ABO-адсетов — отдельная задача (нужно понять, запускать все адсеты кампании или выборочно).

## Порядок реализации

### Этап 0: Верификация fbtool (1 час)
- [ ] Залогировать сырой JSON от `/ajax/get-statistics` для аккаунта с ABO-кампанией
- [ ] Проверить наличие полей: `adset_id`, `adset_name`, `adset_daily_budget`, `adset_effective_status`
- [ ] Проверить `set_budget` с adset_id вместо campaign_id (на тестовой кампании)
- [ ] Если adset-полей нет в JSON — проверить `POST /site/set-statistics-mode` → `adsets`

### Этап 1: fbtool + keitaro клиенты
- [ ] `FbtoolAdset` dataclass
- [ ] Парсинг adset-данных из JSON (или отдельный запрос)
- [ ] `KeitaroClient.get_conversions_by_adset()` + пагинация
- [ ] Тесты парсинга

### Этап 2: campaign_checker + action_executor
- [ ] `_process_adset()` — обработка адсета
- [ ] `_sync_adset()` — синхронизация в DB
- [ ] action_executor: поддержка adset ID
- [ ] DB миграция (индекс)
- [ ] Тесты

### Этап 3: Frontend
- [ ] Колонка budget_level в таблице кампаний
- [ ] Группировка адсетов под кампанией
- [ ] Фильтр CBO/ABO

## Риски

| Риск | Митигация |
|------|-----------|
| fbtool JSON не содержит adset-полей | Альтернатива: `set-statistics-mode=adsets` + отдельный запрос. Удвоит кол-во запросов |
| `set_budget`/`stop` не работает с adset ID | Проверить на тестовой кампании. Если нет — нужен другой endpoint (возможно `POST /task/budget` с другим типом objects) |
| Keitaro sub_id_3 пустой для старых кампаний | Лиды по адсету будут только для новых кампаний с `adset_id={{adset.id}}`. Для старых — fallback на fbtool leads |
| Разные пороги для адсетов | На этапе 1 используем те же пороги. Если нужно — добавить отдельный rule_set с `budget_level=adset` |
| Один адсет в ABO остановлен, другие работают | Корректно — каждый адсет независимая строка в DB, rule engine обрабатывает каждый отдельно |
