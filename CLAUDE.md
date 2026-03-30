# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

FB Budget Manager — система автоматического управления бюджетами рекламных кампаний Facebook. Тянет лиды из Keitaro Tracker, расходы из fbtool.pro, и по "лестнице" правил повышает бюджеты успешным кампаниям или останавливает убыточные.

## Команды

```bash
# Backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev

# Тесты (все)
cd backend && pytest tests/ -v

# Один тест
cd backend && pytest tests/test_rule_engine.py -v
cd backend && pytest tests/test_rule_engine.py::TestCPCStop -v

# Docker (продакшн)
docker compose up -d --build

# Деплой на сервер
bash deploy.sh
```

## Стиль работы

- Перед реализацией крупной фичи — сначала план в `docs/plans/`, потом код
- Мелкие баг-фиксы и правки — сразу делать, без плана
- Объяснения и комментарии в коде — кратко, по существу. Не лить воду
- Все ответы — на русском

## Архитектура

### Два фоновых процесса (APScheduler, max_instances=1)

1. **CampaignChecker** (каждые 10 мин) — основной цикл:
   `FbtoolClient → KeitaroClient → RuleEngine → ActionExecutor → DB + Telegram`

2. **AutoLauncher** (cron) — перезапуск остановленных кампаний:
   - Анализ в 23:00 MSK: классификация кампаний → запись в `auto_launch_queue`
   - Запуск в 04:00 MSK: выполнение очереди (budget + resume через fbtool)

Оба создаются в `main.py:lifespan()` с `DatabaseService.admin()` (service role, обходит RLS).

### Ключевые потоки данных

**Маппинг лидов**: Keitaro `sub_id_4` = Facebook Ad ID (`{{ad.id}}`). Маппинг ad_id → campaign_id через fbtool. Если Keitaro недоступен — fallback на лиды из fbtool.

**Multi-tenant**: Все запросы скоупятся через `user_id`. RLS в Supabase + app-level фильтрация в `DatabaseService`. Фоновые задачи итерируют по всем юзерам через `get_all_user_settings()`.

**Шифрование**: Все чувствительные поля (access_token, cookie, proxy_password, fbtool_cookies) шифруются Fernet перед записью в БД. При чтении — дешифруются в сервисах.

### rule_engine.py — чистая функция

Принимает `CampaignState`, возвращает `Action`. Никаких HTTP-запросов, никакой записи в БД. Полностью покрыт тестами (60+ кейсов в `test_rule_engine.py`). При изменении логики лестницы — обязательно обновлять тесты.

Правила из БД загружаются через `parse_db_rules()` → kwargs для `evaluate()`.

### API (FastAPI)

Все роутеры в `app/api/`, подключаются в `main.py` под `/api/v1/{resource}`.
Auth: Supabase JWT → `get_db_for_user` dependency → `DatabaseService(user_id)`.
Чувствительные поля маскируются `***` в ответах, пропускаются при обновлении если `***`.

### Frontend (React + Vite)

React Router v6: `/login`, `/`, `/accounts`, `/campaigns`, `/rules`, `/logs`, `/settings`, `/generator`, `/auto-launcher`.
Данные: React Query хуки (`useAccounts`, `useCampaigns`, ...). API: axios с JWT interceptor.

## Правила

### Всегда
- Все HTTP-запросы к Facebook — ТОЛЬКО через прокси аккаунта с его cookie/token/useragent
- Логировать ВСЕ действия системы в action_logs (и успешные, и неуспешные)
- Rate limiting: не более 1 запроса/сек на FB-аккаунт (asyncio.Semaphore)
- Timezone: Europe/Moscow для всех расчётов "сегодня"

### Никогда
- НЕ хранить токены/cookie/пароли в открытом виде в БД
- НЕ делать запросы к Facebook без прокси — аккаунт заблокируют
- НЕ перезапускать остановленные лестницей кампании автоматически — только вручную
- НЕ запускать параллельные циклы проверки (max_instances=1 в APScheduler)
- НЕ выполнять действия в Facebook без записи в action_logs

### fbtool.pro-специфика
- Реверс-инжиниринг внутренних запросов (не официальный API — лимит 100/день)
- Auth: cookie `_identity` (30 дней) + `PHPSESSID` + `_csrf`. hCaptcha при логине — только ручной вход
- Чтение: GET HTML-страниц → парсинг BeautifulSoup. Запись: POST с CSRF-токеном
- fbtool использует **Facebook campaign ID напрямую** (нет своих internal ID для кампаний)
- При истечении cookie — уведомление в Telegram. Документация: `docs/plans/2026-03-22-fbtool-migration.md`

### Keitaro-специфика
- **Internal panel API** (`POST /admin/?object=reports.build`), НЕ documented Admin API
- Auth: session cookie, логин через `POST /admin/?object=auth.login`
- Лиды через `grouping: ["sub_id_4"]`, метрика: поле `conversions`
- Circuit breaking: логин блокируется на 60с после 429 (KeitaroLoginBlocked)
- Документация: `docs/api-reference-keitaro.md`

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

Плюс ранний стоп по CPC: 0 лидов + spend >= $2.50 + CPC > $0.45 → STOP.
Cooldown: бюджет не повышается, если последнее изменение < 1 часа назад.

## Стек

- **Backend**: Python 3.11+, FastAPI, APScheduler, httpx + httpx-socks, Pydantic, loguru, tenacity, cryptography, beautifulsoup4
- **Frontend**: React 18+, TypeScript, Vite, TanStack Query, Tailwind CSS + shadcn/ui, Recharts, React Hook Form + Zod
- **DB**: Supabase (PostgreSQL) с RLS
- **Deploy**: Docker Compose на VPS

## Известные ограничения

- **Только CBO**: ABO-кампании (бюджет на уровне адсета) не поддержаны
- **panel_client.py**: deprecated, старый клиент для 2KK Panel. Заменён на fbtool_client.py
- **hide_comments**: есть в модели fb_accounts, но логика не реализована
