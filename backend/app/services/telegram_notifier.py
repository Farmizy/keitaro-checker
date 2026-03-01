"""Telegram notification service — sends alerts on STOP and errors."""

import httpx
from loguru import logger


class TelegramNotifier:

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10)

    async def send(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.debug("Telegram not configured, skipping notification")
            return False

        url = self.API_URL.format(token=self.bot_token)
        try:
            resp = await self._client.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            resp.raise_for_status()
            logger.info(f"Telegram notification sent to {self.chat_id}")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def close(self):
        await self._client.aclose()
