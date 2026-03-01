# Keitaro Panel API Reference

Результаты reverse-engineering сессии через Playwright (2026-03-01).

## Базовые URL

- **Panel**: `https://pro1.trk.dev/admin/`
- **Internal API**: `https://pro1.trk.dev/admin/?object=<action>`
- **Documented API** (`/admin_api/v1/`): требует API-ключ, у нас нет доступа → не используем

## Аутентификация

Сессионная cookie. Логин через:

```
POST /admin/?object=auth.login
Content-Type: application/json

{"login": "username", "password": "password"}
```

Результат: cookie `keitaro=<session_id>` — отправляется автоматически во всех последующих запросах.

## Endpoints

### Построение отчёта (главный endpoint)

```
POST /admin/?object=reports.build
Content-Type: application/json
Cookie: keitaro=<session_id>
```

**Request Body (группировка по sub_id_4 — FB ad ID):**
```json
{
  "range": {
    "interval": "today",
    "timezone": "Europe/Moscow"
  },
  "columns": [],
  "metrics": ["clicks", "campaign_unique_clicks", "conversions", "roi_confirmed"],
  "grouping": ["sub_id_4"],
  "filters": [],
  "summary": true,
  "limit": 100,
  "offset": 0
}
```

**Response:**
```json
{
  "rows": [
    {
      "sub_id_4": "120238209447230519",
      "clicks": 462,
      "campaign_unique_clicks": 350,
      "conversions": 10,
      "roi_confirmed": 111.64
    },
    {
      "sub_id_4": "120240131659510277",
      "clicks": 303,
      "campaign_unique_clicks": 247,
      "conversions": 5,
      "roi_confirmed": 177.93
    }
  ],
  "summary": {
    "clicks": 6682,
    "campaign_unique_clicks": 2938,
    "conversions": 26,
    "roi_confirmed": 49.03,
    "sub_id_4": null
  },
  "total": 43,
  "meta": {
    "body": 0,
    "summary": 0,
    "count": 0
  }
}
```

### Доступные параметры

**range.interval**:
- `"today"` — сегодня
- `"yesterday"` — вчера
- `"7_days_ago"` — последние 7 дней
- Также можно указать конкретные даты (формат не перехвачен)

**metrics** (доступные метрики):
- `"clicks"` — клики
- `"campaign_unique_clicks"` — уникальные клики кампании
- `"conversions"` — конверсии (все типы)
- `"roi_confirmed"` — ROI подтверждённый

**grouping** (группировка):
- `"campaign"` — по кампании Keitaro
- `"sub_id_4"` — по sub_id_4 (FB ad ID)
- Другие доступные: `"sub_id"`, `"sub_id_2"`, `"sub_id_3"`, ..., `"sub_id_15"` и т.д.

**filters** (фильтры):
```json
{
  "name": "campaign_id",
  "operator": "IN_LIST",
  "expression": [40248, 37228]
}
```

### Лог конверсий

```
POST /admin/?object=conversions.log
Content-Type: application/json
Cookie: keitaro=<session_id>
```

Возвращает индивидуальные конверсии (не агрегированные).

### Кампании со статистикой

```
POST /admin/?object=campaigns.withStats
```

### Другие endpoints

```
GET  /admin/?object=campaigns.listAsOptions   — список кампаний для выбора
GET  /admin/?object=reports.definition         — определение доступных метрик/группировок
GET  /admin/?object=system.trackerInfo         — информация о трекере
```

## Sub-параметры (маппинг)

| Sub | Содержимое | Placeholder в FB |
|-----|-----------|-----------------|
| sub_id_4 | Facebook Ad ID | `{{ad.id}}` |
| sub_id_4 value example | `120238209447230519` | |

**Важно:** `sub_id_4` содержит **Ad ID** (уровень объявления), не Campaign ID. Одна FB-кампания может иметь несколько объявлений. Для подсчёта лидов кампании нужно:
1. Из 2KK Panel API получить список ads для каждой кампании, ИЛИ
2. Маппить ad_id → campaign_id по данным 2KK Panel

## Важные замечания

1. **Сессия**: используется cookie-based auth, сессия может истекать. Нужна логика re-login при 401/403
2. **sub_id_4 = Ad ID**: не путать с Campaign ID. Нужен маппинг ad → campaign
3. **`{{ad.id}}`**: незаменённые плейсхолдеры попадают как строка `"{{ad.id}}"` — нужно фильтровать
4. **`""` (пустой sub_id_4)**: конверсии без sub_id_4 — игнорировать
5. **Timezone**: Europe/Moscow — совпадает с нашей системой
6. **`conversions`** — все конверсии без фильтра по статусу (lead, sale, etc.)
