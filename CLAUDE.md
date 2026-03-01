# FB Budget Manager

Система автоматического управления бюджетами рекламных кампаний Facebook. Тянет лиды из Keitaro Tracker, расходы из Facebook, и по "лестнице" правил повышает бюджеты успешным кампаниям или останавливает убыточные. Проверка каждые 10 минут.

## Запуск

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # заполнить SUPABASE_URL, SUPABASE_KEY, KEITARO_URL, KEITARO_LOGIN, KEITARO_PASSWORD, PANEL_JWT, ENCRYPTION_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Тесты
```bash
cd backend
pytest tests/ -v
```

### Docker (продакшн)
```bash
docker compose up -d
```

## Структура

```
backend/
  app/
    main.py              — FastAPI + APScheduler lifespan
    config.py            — pydantic-settings, переменные из .env
    api/                 — REST endpoints (accounts, campaigns, rules, logs, dashboard, scheduler)
    models/              — Pydantic-модели данных
    schemas/             — Request/Response схемы для API
    services/            — Бизнес-логика:
      panel_client.py      — HTTP-клиент к 2KK Panel API (fbm.adway.team/api/)
      keitaro_client.py    — Keitaro Internal Panel API (лиды через sub_id_4)
      rule_engine.py       — Чистая логика лестницы правил (без побочных эффектов)
      campaign_checker.py  — Оркестратор 10-мин цикла проверки
      action_executor.py   — Исполнитель действий (бюджет/пауза)
      database_service.py  — CRUD с Supabase
      scheduler_service.py — Обёртка APScheduler
      telegram_notifier.py — Уведомления в Telegram
    core/                — Шифрование, исключения, логирование
    db/                  — Supabase-клиент, SQL-миграции
  tests/               — Unit-тесты (pytest)

frontend/
  src/
    api/               — HTTP-клиент + модули по endpoint'ам
    components/        — React-компоненты по доменам (Accounts, Campaigns, Rules, Logs, Dashboard)
    pages/             — Страницы (DashboardPage, AccountsPage, CampaignsPage, RulesPage, LogsPage)
    hooks/             — React-хуки (useAccounts, useCampaigns...)
    types/             — TypeScript-типы
```

## Стиль работы

- Перед реализацией крупной фичи — сначала план в `docs/plans/`, потом код
- Мелкие баг-фиксы и правки — сразу делать, без плана
- Объяснения и комментарии в коде — кратко, по существу. Не лить воду
- Все ответы — на русском

## Правила

### Всегда
- Все чувствительные данные (access_token, cookie, proxy_password) шифровать через Fernet перед записью в БД
- Все HTTP-запросы к Facebook — ТОЛЬКО через прокси аккаунта с его cookie/token/useragent
- rule_engine.py — чистая функция без побочных эффектов. Никаких HTTP-запросов, никакой записи в БД внутри
- Логировать ВСЕ действия системы в action_logs (и успешные, и неуспешные)
- Unit-тесты для rule_engine обязательны при любом изменении логики лестницы
- Rate limiting: не более 1 запроса/сек на FB-аккаунт (asyncio.Semaphore)
- Timezone: Europe/Moscow для всех расчётов "сегодня"

### Никогда
- НЕ хранить токены/cookie/пароли в открытом виде в БД
- НЕ делать запросы к Facebook без прокси — аккаунт заблокируют
- НЕ перезапускать остановленные лестницей кампании автоматически — только вручную
- НЕ запускать параллельные циклы проверки (max_instances=1 в APScheduler)
- НЕ коммитить .env файлы
- НЕ выполнять действия в Facebook без записи в action_logs

### Keitaro-специфика
- Keitaro использует **internal panel API** (`POST /admin/?object=reports.build`), НЕ documented Admin API (`/admin_api/v1/` — нет API-ключа)
- Auth: session cookie (`keitaro=<session_id>`), логин через `POST /admin/?object=auth.login`
- Лиды получаем через `POST /admin/?object=reports.build` с `grouping: ["sub_id_4"]`
- sub_id_4 = Facebook Ad ID (`{{ad.id}}`). Маппинг ad_id → campaign_id через 2KK Panel API
- Метрика лидов: поле `conversions` (все конверсии без фильтра по статусу)
- Лиды и spend считаются за СЕГОДНЯ (interval: "today", timezone: Europe/Moscow), лестница сбрасывается ежедневно
- Полная документация: `docs/api-reference-keitaro.md`

### Лестница правил (дефолтная)
| Spend сегодня | Лиды сегодня | Действие |
|---------------|-------------|----------|
| >= $8 | 0 | STOP |
| >= $8 | 1 | Ждать до $16 |
| >= $16 | 2 | Бюджет → $75, ждать до $24 |
| >= $24 | 3 | Ждать до $32 |
| >= $32 | 4 | Бюджет → $150, ждать до $40 |
| >= $40 | 5 | Ждать до $48 |
| >= $48 | 5+ CPL>$10 | STOP |
| >= $48 | 6 | Бюджет → $250 |
| >= $48 | 7+ | Manual review |

## Стек

- **Backend**: Python 3.11+, FastAPI, APScheduler, httpx + httpx-socks, Pydantic, loguru, tenacity, cryptography
- **Frontend**: React 18+, TypeScript, Vite, TanStack Query, Tailwind CSS + shadcn/ui, Recharts, React Hook Form + Zod
- **DB**: Supabase (PostgreSQL)
- **Deploy**: Docker Compose на VPS

## Известные проблемы и ошибки

### ABO-кампании не поддержаны
Сейчас система работает только с CBO (бюджет на уровне кампании). Для ABO нужно:
1. Добавить `{{adset_id}}` в placeholder sub3 в Keitaro
2. Реализовать группировку по adset_id
3. Управлять бюджетом на уровне адсета

### Скрытие комментариев — отложено
Функция hide_comments есть в модели fb_accounts, но логика не реализована.
