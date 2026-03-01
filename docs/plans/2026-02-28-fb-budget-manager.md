# План реализации: FB Budget Manager

## Обзор

Система автоматического управления бюджетами Facebook Ads. Забирает лиды из Keitaro (поле `conversions`, группировка по `sub_id_4` = ad_id, маппинг через 2KK Panel), расходы из 2KK Panel API (`fbm.adway.team/api/`), и по лестнице правил каждые 10 минут повышает бюджеты или останавливает кампании. Один пользователь, один Keitaro, валюта — только USD.

## Архитектура

```
[React + TS + Vite]  <--REST-->  [FastAPI + APScheduler]
                                        |
                         +--------------+--------------+
                         |              |              |
                   [Keitaro API]  [2KK Panel API]  [Supabase]
                                  fbm.adway.team
```

Монолит: один процесс FastAPI = REST API + APScheduler. При росте — выносим воркер.

## Принятые решения

| Вопрос | Решение |
|--------|---------|
| БД | Supabase через MCP, миграции через MCP |
| RLS | Включён + политики (проверка наличия JWT) |
| Auth | Supabase JWT middleware на бэкенде |
| Тенантность | Один пользователь |
| FB API | **2KK Panel API** (`fbm.adway.team/api/`) — reverse-engineered, полностью готов |
| Spend | Из 2KK Panel API (`stats.spent`) |
| Валюта | Только USD |
| Keitaro лиды | Поле `conversions` |
| Keitaro инстанс | Один на все аккаунты |
| Timezone | Europe/Moscow (Keitaro совпадает) |
| Повышение бюджета | При достижении кол-ва лидов, **без привязки к spend** |
| Кулдаун | 1 час на уровне кампании после повышения бюджета |
| Кулдаун — тип | Проверяем данные, но не меняем бюджет. STOP работает всегда |
| Понижение бюджета | **Никогда**. Если ручной бюджет > правила → не трогаем |
| Идемпотентность | Если current_budget == target → пропускаем |
| Rule set | Один дефолтный для всех кампаний |
| Ошибки в цикле | Продолжаем с остальными аккаунтами |
| Синхр. статуса | Проверяем реальный статус через Panel API каждый цикл |
| Начальный бюджет | Уже стоит в FB (пользователь ставит сам) |
| Layout | Sidebar слева |
| Обновления | TanStack Query refetchInterval ~30 сек |
| Мобильность | Да, адаптив |
| Фильтры | По аккаунту + статусу |
| Telegram | Только STOP и ошибки |
| Docker | backend + nginx (фронт — статика) |

## 2KK Panel API (reverse-engineered)

Полная документация: `docs/api-reference-2kk-panel.md`

| Действие | Метод | URL | Тело запроса |
|----------|-------|-----|--------------|
| Список кампаний | POST | `/api/campaigns` | `{filter: {startDate, endDate, withSpent}, page, limit}` |
| Список аккаунтов | POST | `/api/accounts` | `{filter: {startDate, endDate, withSpent}, page, limit}` |
| Изменить бюджет | POST | `/api/campaigns/{id}/change_budget` | `{dailyBudget: 30}` |
| Пауза/Возобновление | POST | `/api/campaigns/update` | `{campaignsIds: [id], status: "PAUSED"}` |

- Base URL: `https://fbm.adway.team/api/`
- Auth: `Authorization: Bearer <JWT>` (JWT от Google OAuth через `panel.adway.team`)
- `{id}` — внутренний ID панели (`data[].id`), НЕ Facebook campaign ID
- Spend в ответе: `stats.spent` (без налога), `stats.spentWithTax` (с налогом)

## Keitaro API (reverse-engineered)

Полная документация: `docs/api-reference-keitaro.md`

**Тип**: Internal Panel API (`POST /admin/?object=<action>`), НЕ documented Admin API (нет API-ключа).
**Auth**: Session cookie `keitaro=<session_id>`, логин через `POST /admin/?object=auth.login` с `{login, password}`.

| Действие | Метод | URL | Тело запроса |
|----------|-------|-----|--------------|
| Отчёт | POST | `/admin/?object=reports.build` | `{range, metrics, grouping, ...}` |
| Логин | POST | `/admin/?object=auth.login` | `{login, password}` |

### Sub-параметры
| Sub | Содержимое | Placeholder |
|-----|-----------|-------------|
| sub_id_4 | Facebook Ad ID | `{{ad.id}}` |

**Важно**: sub_id_4 содержит **Ad ID**, не Campaign ID. Маппинг ad→campaign через 2KK Panel API (поле `campaignId` в ответе кампаний).

## Схема БД (Supabase)

### fb_accounts
```
id UUID PK
name TEXT
account_id TEXT UNIQUE          -- act_XXXXX
panel_account_id INT            -- внутренний ID в 2KK Panel
access_token TEXT               -- encrypted
cookie TEXT                     -- encrypted
useragent TEXT
proxy_type ENUM(socks5/http/https)
proxy_host TEXT
proxy_port INT
proxy_login TEXT
proxy_password TEXT             -- encrypted
hide_comments BOOLEAN           -- отложено
is_active BOOLEAN
last_check_at TIMESTAMPTZ
last_error TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### campaigns
```
id UUID PK
fb_account_id UUID FK -> fb_accounts
fb_campaign_id TEXT             -- Facebook campaign ID (120238703108910240)
panel_campaign_id INT           -- внутренний ID в 2KK Panel (48019)
fb_campaign_name TEXT
fb_adset_id TEXT                -- для ABO (будущее)
budget_level ENUM(campaign/adset)
status ENUM(active/paused/stopped)
current_budget NUMERIC(10,2)
total_spend NUMERIC(10,2)
leads_count INT
cpl NUMERIC(10,2)
is_managed BOOLEAN
last_budget_change_at TIMESTAMPTZ  -- для кулдауна 1ч
last_keitaro_sync TIMESTAMPTZ
last_fb_sync TIMESTAMPTZ
notes TEXT
UNIQUE(fb_account_id, fb_campaign_id)
```

### rule_sets
```
id UUID PK
name TEXT
description TEXT
is_default BOOLEAN
```

### rule_steps
```
id UUID PK
rule_set_id UUID FK -> rule_sets
step_order INT
spend_threshold NUMERIC(10,2)
leads_min INT
leads_max INT
max_cpl NUMERIC(10,2)
action ENUM(budget_increase/campaign_stop/campaign_pause/manual_review_needed)
new_budget NUMERIC(10,2)
next_spend_limit NUMERIC(10,2)
description TEXT
UNIQUE(rule_set_id, step_order)
```

### action_logs
```
id UUID PK
campaign_id UUID FK
fb_account_id UUID FK
action_type ENUM
rule_step_id UUID FK
details JSONB                   -- {spend, leads, cpl, old_budget, new_budget, reason}
success BOOLEAN
error_message TEXT
created_at TIMESTAMPTZ
```

### check_runs
```
id UUID PK
status ENUM(pending/running/completed/failed)
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ
campaigns_checked INT
actions_taken INT
errors_count INT
details JSONB
```

## Лестница правил (финальная логика)

Период: spend + лиды за СЕГОДНЯ (Europe/Moscow). Сбрасывается ежедневно.
Бюджет: daily budget. Стартовый: ~$30 (ставит пользователь).
Лид: любая конверсия в Keitaro (поле `conversions`).
Остановленные кампании НЕ перезапускаются автоматически.

### Повышение бюджета (по кол-ву лидов, без привязки к spend)
| Лиды | Действие | Кулдаун |
|------|----------|---------|
| 2 | Бюджет → $75 | 1 час |
| 4 | Бюджет → $150 | 1 час |
| 6 | Бюджет → $250 | 1 час |

### STOP (по spend, если лидов не хватает)
| Spend | Лиды | Действие |
|-------|-------|----------|
| >= $8 | 0 | STOP |
| >= $16 | ≤ 1 | STOP |
| >= $24 | ≤ 2 | STOP |
| >= $32 | ≤ 3 | STOP |
| >= $40 | ≤ 4 | STOP |
| >= $48 | 5+ и CPL > $10 | STOP |

### Остальное
| Условие | Действие |
|---------|----------|
| 7+ лидов | Manual review (Telegram) |
| Кулдаун активен | Проверяем, но бюджет не меняем (STOP работает) |
| Ручной бюджет > правила | Не трогаем |

### Алгоритм rule_engine (псевдокод)
```python
def evaluate(spend, leads, current_budget, last_budget_change_at, now):
    # 1. STOP проверки (всегда, даже в кулдаун)
    thresholds = [(8, 0), (16, 1), (24, 2), (32, 3), (40, 4)]
    for spend_limit, max_leads in thresholds:
        if spend >= spend_limit and leads <= max_leads:
            return Action.STOP

    # CPL-стоп
    if spend >= 48 and leads >= 5:
        cpl = spend / leads
        if cpl > 10:
            return Action.STOP

    # 7+ лидов — manual review
    if leads >= 7:
        return Action.MANUAL_REVIEW

    # 2. Проверка кулдауна (только для бюджетных действий)
    if last_budget_change_at and (now - last_budget_change_at) < 1 hour:
        return Action.WAIT  # кулдаун активен

    # 3. Повышение бюджета (только вверх, никогда вниз)
    budget_steps = [(6, 250), (4, 150), (2, 75)]
    for min_leads, target_budget in budget_steps:
        if leads >= min_leads and current_budget < target_budget:
            return Action.SET_BUDGET(target_budget)

    return Action.WAIT  # ничего не делаем
```

## API Endpoints (наш бэкенд)

### /api/v1/accounts
- `GET /` — список
- `POST /` — создать
- `GET /{id}` — детали
- `PUT /{id}` — обновить
- `DELETE /{id}` — удалить
- `POST /{id}/test` — проверить подключение

### /api/v1/campaigns
- `GET /` — список с фильтрами (аккаунт, статус)
- `GET /{id}` — детали с историей
- `PUT /{id}` — обновить настройки
- `POST /{id}/pause` — пауза
- `POST /{id}/resume` — возобновление
- `POST /sync` — синхронизация с Panel API

### /api/v1/rules
- `GET /` — список наборов
- `POST /` — создать
- `GET /{id}` — детали с шагами
- `PUT /{id}` — обновить
- CRUD для steps внутри набора

### /api/v1/logs
- `GET /actions` — лог действий
- `GET /checks` — история циклов

### /api/v1/dashboard
- `GET /stats` — агрегаты
- `GET /recent-actions` — последние 20 действий

### /api/v1/scheduler
- `GET /status` — статус
- `POST /trigger` — ручной запуск
- `POST /pause` / `POST /resume`

## Фронтенд

Стек: React 18+, TypeScript, Vite, TanStack Query, Tailwind + shadcn/ui, Recharts.
Тема: тёмная. Авторизация: Supabase Auth. Sidebar слева. Мобильная адаптивность.
Обновление данных: TanStack Query refetchInterval ~30 сек.

Страницы:
1. **Dashboard** — карточки (spend, leads, active, paused), график, последние действия, статус планировщика
2. **Accounts** — CRUD FB-аккаунтов (форма: name, token, cookie, ua, proxy)
3. **Campaigns** — таблица с фильтрами (аккаунт, статус), цветовое кодирование CPL, pause/resume
4. **Rules** — визуальный редактор лестницы
5. **Logs** — таблица действий с пагинацией
6. **Settings** — Keitaro API, Telegram, интервал проверки

## Фазы реализации

### Фаза 1: Фундамент
- [ ] Структура проекта backend + frontend
- [ ] FastAPI скелет (`main.py`, `config.py`, lifespan, CORS)
- [ ] SQL-миграции через Supabase MCP (все таблицы)
- [ ] Pydantic models + schemas
- [ ] Шифрование Fernet (`core/encryption.py`)
- [ ] JWT middleware (`core/auth.py`) — верификация Supabase JWT
- [ ] CRUD `fb_accounts` (API + database_service)
- [ ] RLS-политики на все таблицы

**Файлы:**
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/core/encryption.py`
- `backend/app/core/auth.py`
- `backend/app/models/`
- `backend/app/schemas/`
- `backend/app/services/database_service.py`
- `backend/app/api/accounts.py`

### Фаза 2: Клиенты API
- [ ] `KeitaroClient` — Internal Panel API (`POST /admin/?object=reports.build`), grouping по `sub_id_4`, поле `conversions`
  - Auth: session cookie, логин через `POST /admin/?object=auth.login`
  - Нужна логика re-login при истечении сессии
  - Ref: `docs/api-reference-keitaro.md`
- [ ] `PanelClient` — HTTP-клиент для 2KK Panel API (`fbm.adway.team/api/`):
  - `get_campaigns(start_date, end_date, page, limit)` — `POST /api/campaigns`
  - `get_accounts(start_date, end_date)` — `POST /api/accounts`
  - `set_budget(internal_id, daily_budget)` — `POST /api/campaigns/{id}/change_budget`
  - `update_campaign_status(campaign_ids, status)` — `POST /api/campaigns/update`
  - Auth: Bearer JWT (хранится в config/env)
- [ ] Unit-тесты для клиентов (моки)

**Файлы:**
- `backend/app/services/keitaro_client.py`
- `backend/app/services/panel_client.py`
- `backend/tests/test_keitaro_client.py`
- `backend/tests/test_panel_client.py`

### Фаза 3: Движок правил
- [ ] `RuleEngine` — чистая функция (без побочных эффектов)
- [ ] Логика: STOP проверки → кулдаун → повышение бюджета
- [ ] Никогда не понижать бюджет
- [ ] 15+ unit-тестов на каждый сценарий
- [ ] Seed данные Default Ladder в `rule_steps`

**Файлы:**
- `backend/app/services/rule_engine.py`
- `backend/tests/test_rule_engine.py`

### Фаза 4: Планировщик и оркестрация
- [ ] `CampaignCheckerService` — 10-мин цикл:
  1. Для каждого активного аккаунта
  2. Получить кампании из 2KK Panel API (+ синхр. статус, spend)
  3. Получить лиды из Keitaro
  4. Для каждой кампании: вызвать `RuleEngine.evaluate()`
  5. Выполнить действие через `ActionExecutor`
  6. Записать в `action_logs`
- [ ] `ActionExecutor` — исполнитель (budget/pause/stop) через PanelClient
- [ ] `SchedulerService` + APScheduler (max_instances=1)
- [ ] API: `/scheduler/status`, `/scheduler/trigger`, `/scheduler/pause`, `/scheduler/resume`
- [ ] При ошибке одного аккаунта — продолжаем с остальными

**Файлы:**
- `backend/app/services/campaign_checker.py`
- `backend/app/services/action_executor.py`
- `backend/app/services/scheduler_service.py`
- `backend/app/api/scheduler.py`

### Фаза 5: Фронтенд
- [ ] React + Vite + Router + TanStack Query + shadcn/ui (тёмная тема)
- [ ] Supabase Auth (login/password)
- [ ] Sidebar layout, мобильная адаптивность
- [ ] refetchInterval ~30 сек
- [ ] Страница Dashboard
- [ ] Страница Accounts
- [ ] Страница Campaigns (фильтры: аккаунт, статус)
- [ ] Страница Rules
- [ ] Страница Logs
- [ ] Страница Settings

**Файлы:**
- `frontend/src/pages/`
- `frontend/src/components/`
- `frontend/src/api/`
- `frontend/src/hooks/`

### Фаза 6: Telegram + Docker
- [ ] `TelegramNotifier` — отправка при STOP и ошибках
- [ ] Docker Compose: backend + nginx (фронт → статика)
- [ ] Dockerfile для backend (Python 3.11)
- [ ] nginx.conf (статика + прокси API)

**Файлы:**
- `backend/app/services/telegram_notifier.py`
- `docker-compose.yml`
- `Dockerfile` (backend)
- `frontend/Dockerfile` (multi-stage build)
- `nginx/nginx.conf`

### Отложено
- Скрытие комментариев в FB
- Поддержка ABO (бюджет на адсете)
- Несколько наборов правил (пресеты)

## Verification

### Backend
```bash
cd backend && pytest tests/ -v
uvicorn app.main:app --reload
# Swagger: http://localhost:8000/docs
# POST /api/v1/scheduler/trigger — ручная проверка
```

### Frontend
```bash
cd frontend && npm run dev
# Проверить все страницы: Dashboard, Accounts, Campaigns, Rules, Logs, Settings
# Проверить мобильный вид (DevTools responsive)
```

### E2E
1. Залогиниться через Supabase Auth
2. Создать FB-аккаунт через панель
3. Синхронизировать кампании
4. Запустить ручную проверку (`POST /scheduler/trigger`)
5. Проверить action_logs
6. Проверить Telegram-уведомление при STOP
7. Проверить кулдаун — после повышения бюджета следующий цикл не меняет бюджет

## Критические файлы
- `backend/app/services/rule_engine.py` — бизнес-логика лестницы
- `backend/app/services/campaign_checker.py` — оркестратор цикла
- `backend/app/services/panel_client.py` — интеграция с 2KK Panel API
- `backend/app/services/keitaro_client.py` — интеграция с Keitaro
- `backend/app/main.py` — FastAPI + APScheduler
- `docs/api-reference-2kk-panel.md` — справочник 2KK Panel API
- `docs/api-reference-keitaro.md` — справочник Keitaro Internal API
