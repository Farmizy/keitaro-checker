# 2KK Panel API Reference

Результаты reverse-engineering сессии через Playwright (2026-03-01).

## Базовые URL

- **Panel frontend**: `https://panel.2kk.team`
- **Panel API (auth)**: `https://panel.adway.team/api/`
- **FB Manager API**: `https://fbm.adway.team/api/`

## Аутентификация

- Google OAuth через `POST panel.adway.team/api/auth/google`
- Результат: JWT-токен
- Все запросы к `fbm.adway.team` — с заголовком:
  ```
  Authorization: Bearer <JWT>
  Content-Type: application/json; charset=UTF-8
  Origin: https://panel.2kk.team
  Referer: https://panel.2kk.team/
  ```

## Endpoints

### Список кампаний

```
POST https://fbm.adway.team/api/campaigns
```

**Request Body:**
```json
{
  "filter": {
    "startDate": "2026-03-01",
    "endDate": "2026-03-01",
    "withSpent": false
  },
  "page": 1,
  "limit": 20
}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 48019,                          // internal panel ID (используется в change_budget, update)
      "campaignId": "120238703108910240",    // Facebook campaign ID
      "name": "02 02 Суставы/HU/UltraVix/...",
      "dailyBudget": "30.00",
      "lifetimeBudget": 0,
      "bidStrategy": "LOWEST_COST_WITHOUT_CAP",
      "objective": "OUTCOME_LEADS",
      "effectiveStatus": "PAUSED",           // PAUSED | ACTIVE | ...
      "user": { "name": "Родион Алексинцев" },
      "account": { "name": "ph1", "status": "PROXY_ERROR" },
      "stats": {
        "impressions": 0,
        "linkClicks": 0,
        "results": 0,
        "cpa": 0,
        "ctr": 0,
        "cpm": null,
        "cpc": null,
        "spent": 0,                          // spend сегодня (без налога)
        "spentWithTax": 0,
        "tax": 0,
        "lead": 0,                           // лиды по данным FB
        "leadCost": 0,
        "webLead": 0,
        "completeRegistration": 0,
        "purchase": 0
      },
      "cab": {
        "name": "VH 2034",
        "currency": "USD"
      }
    }
  ],
  "stats": { ... },
  "pagination": { ... }
}
```

### Список аккаунтов

```
POST https://fbm.adway.team/api/accounts
```

**Request Body:**
```json
{
  "filter": {
    "startDate": "2026-03-01",
    "endDate": "2026-03-01",
    "withSpent": false
  },
  "page": 1,
  "limit": 20
}
```

**Response (из предыдущей сессии):**
```json
{
  "success": true,
  "data": [
    {
      "id": 2086,
      "name": "ph1",
      "status": "ACTIVE",
      "userAgent": "...",
      "accessToken": "...",
      "cookies": "...",
      "tax": 0,
      "proxy": {
        "ip": "...",
        "port": "...",
        "login": "...",
        "password": "...",
        "type": "socks5"
      },
      "pages": [...]
    }
  ]
}
```

### Изменение бюджета

```
POST https://fbm.adway.team/api/campaigns/{internal_id}/change_budget
```

**Request Body:**
```json
{
  "dailyBudget": 30
}
```

**Response:**
```json
{
  "success": true
}
```

- `internal_id` — это `data[].id` из списка кампаний (например, 48019), НЕ `campaignId`
- `dailyBudget` — число (не строка)

### Пауза / Возобновление кампаний

```
POST https://fbm.adway.team/api/campaigns/update
```

**Request Body (пауза):**
```json
{
  "campaignsIds": [48019],
  "status": "PAUSED"
}
```

**Request Body (возобновление — предположительно):**
```json
{
  "campaignsIds": [48019],
  "status": "ACTIVE"
}
```

**Response:**
Тост "Кампании обновлены" — конкретный формат response не перехвачен.

- Поддерживает массовые операции (массив `campaignsIds`)

### Обновление аккаунта

```
PATCH https://fbm.adway.team/api/accounts/{account_id}
```

Замечен в сетевых логах. Точный формат тела не перехвачен.

### Список прокси

```
GET https://fbm.adway.team/api/proxies?page=1
```

## Важные замечания

1. **Internal ID vs Facebook ID**: Все действия (change_budget, update) используют внутренний ID панели (`data[].id`), а не Facebook campaign ID (`data[].campaignId`)
2. **Spend**: Доступен в `stats.spent` (без налога) и `stats.spentWithTax` (с налогом)
3. **Лиды FB**: `stats.lead` — лиды по данным Facebook. Мы используем лиды из Keitaro, а spend из этого API
4. **Статусы**: `effectiveStatus` может быть `PAUSED`, `ACTIVE` (другие не исследованы)
5. **Фильтрация по дате**: startDate/endDate задают период для статистики (spend, leads и т.д.)
6. **withSpent**: Флаг — возможно фильтрует кампании с расходом. false = показать все
7. **Пагинация**: page + limit стандартные
