"""Проверка: есть ли adset-поля в JSON от fbtool /ajax/get-statistics.

Запуск внутри контейнера: python /app/check_fbtool_adset_fields.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, "/app")  # Docker container path

from datetime import datetime

import httpx


async def main():
    # Читаем cookies из БД (user_settings), а не из .env
    from app.services.database_service import DatabaseService

    db = DatabaseService.admin()
    all_users = db.get_all_user_settings()

    cookies = None
    account_ids = None
    for user in all_users:
        if user.get("fbtool_cookies") and user.get("fbtool_account_ids"):
            cookies = user["fbtool_cookies"]
            account_ids = user["fbtool_account_ids"]
            print(f"User: {user['user_id']}")
            break

    if not cookies:
        print("ERROR: no user with fbtool_cookies found in DB")
        return

    if isinstance(account_ids, str):
        account_ids = json.loads(account_ids)

    account_id = account_ids[0]
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"Account: {account_id}, date: {today}\n")

    url = (
        f"https://fbtool.pro/ajax/get-statistics"
        f"?id={account_id}"
        f"&dates={today}+-+{today}"
        f"&status=all"
        f"&currency=USD"
        f"&adaccount_status=all"
        f"&ad_account_id=all"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url,
            headers={
                "Cookie": cookies,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )

        if resp.status_code in (301, 302):
            print(f"REDIRECT -> {resp.headers.get('location', '?')}")
            print("Сессия истекла — обнови fbtool cookies")
            return

        if resp.status_code != 200:
            print(f"ERROR: HTTP {resp.status_code}")
            print(resp.text[:500])
            return

        data = resp.json()

    if not data or not isinstance(data, list):
        print("Unexpected response format:")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
        return

    all_rows = []
    for group in data:
        all_rows.extend(group.get("rows", []))

    if not all_rows:
        print("Нет строк в ответе (нет активных кампаний сегодня?)")
        return

    row = all_rows[0]

    print(f"=== Всего строк (ad-level): {len(all_rows)} ===\n")

    # Все поля
    print(f"=== Все поля ({len(row)}) ===")
    for key in sorted(row.keys()):
        val = repr(row[key])
        if len(val) > 80:
            val = val[:80] + "..."
        print(f"  {key}: {val}")

    # Adset-поля
    print(f"\n=== Adset-поля ===")
    adset_fields = {k: v for k, v in row.items() if "adset" in k.lower() or "ad_set" in k.lower()}
    if adset_fields:
        for k, v in adset_fields.items():
            print(f"  {k}: {repr(v)}")
    else:
        print("  НЕ НАЙДЕНЫ — возможно нужен другой statistics-mode")

    # Budget-поля
    print(f"\n=== Budget-поля ===")
    for k, v in sorted(row.items()):
        if "budget" in k.lower():
            print(f"  {k}: {repr(v)}")

    # Campaign-поля
    print(f"\n=== Campaign-поля ===")
    for k, v in sorted(row.items()):
        if "campaign" in k.lower():
            print(f"  {k}: {repr(v)}")

    # Проверка CBO vs ABO
    print(f"\n=== CBO/ABO анализ ===")
    campaign_budgets = {}
    for r in all_rows:
        cid = r.get("campaign_id", "?")
        cname = r.get("campaign_name", "?")
        cb = r.get("campaign_daily_budget", "?")
        ab = r.get("adset_daily_budget", r.get("ad_set_daily_budget", "NOT_FOUND"))
        if cid not in campaign_budgets:
            campaign_budgets[cid] = {"name": cname, "campaign_budget": cb, "adset_budget": ab}

    for cid, info in list(campaign_budgets.items())[:10]:
        btype = "ABO" if info["campaign_budget"] in (0, "0", None) else "CBO"
        print(f"  [{btype}] {info['name'][:40]}: campaign_budget={info['campaign_budget']}, adset_budget={info['adset_budget']}")


if __name__ == "__main__":
    asyncio.run(main())
