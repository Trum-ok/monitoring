import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import cached_property
from typing import Any

import httpx
from app.utils.message_templates import build_error_alert_message


class TelegramBot:
    def __init__(
        self,
        token: str,
        chat_id: str,
        throttle_sec: float,
        rate_limit_per_sec: float,
        max_retries: int,
        retry_backoff_max_sec: float,
        parse_mode: str,
        queue_maxsize: int,
        max_traceback_chars: int,
        on_delivered: Callable[[str], Awaitable[None]] | None = None,
    ):
        self.on_delivered = on_delivered
        self.token = token
        self.chat_id = chat_id
        self.throttle_sec = throttle_sec
        self.rate_limit_per_sec = rate_limit_per_sec
        self.max_retries = max_retries
        self.retry_backoff_max_sec = retry_backoff_max_sec
        self.parse_mode = parse_mode
        self.max_traceback_chars = max(1, min(max_traceback_chars, 2048))
        self.session: httpx.AsyncClient | None = None
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_maxsize)
        self.worker_task: asyncio.Task[None] | None = None
        self.logger = logging.getLogger(__name__)

    @cached_property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}/"

    async def start(self) -> None:
        self.logger.info("Starting Telegram bot...")
        if self.session is None:
            self.session = httpx.AsyncClient()
        self.worker_task = asyncio.create_task(self._worker())
        self.logger.info("Telegram bot started")

    async def send_alert(self, payload: dict[str, Any]) -> None:
        """Enqueue alert payload for asynchronous delivery."""
        await self.queue.put(payload)

    async def _worker(self) -> None:
        """Consume queue and send messages with throttling and retry policy."""
        min_send_interval = max(self.throttle_sec, 1.0 / max(self.rate_limit_per_sec, 0.01))

        try:
            while True:
                payload = await self.queue.get()
                text = str(payload.get("text", "")) or build_error_alert_message(
                    payload,
                    max_traceback_chars=self.max_traceback_chars,
                )
                chat_id = int(payload.get("chat_id", self.chat_id))
                parse_mode = str(payload.get("parse_mode", self.parse_mode))

                send_result = await self.send_message_with_retry(text, chat_id, parse_mode)
                if send_result:
                    signature_hash = payload.get("signature_hash")

                    if signature_hash and self.on_delivered is not None:
                        await self.on_delivered(signature_hash)

                self.queue.task_done()
                await asyncio.sleep(min_send_interval)
        except asyncio.CancelledError:
            self.logger.info("Telegram worker cancelled")
            raise

    async def send_message_with_retry(self, message: str, chat_id: int, parse_mode: str) -> bool:
        """Send message with retry strategy for Telegram 429/5xx errors."""
        attempt = 0
        while attempt <= self.max_retries:
            ok, retry_after = await self.send_message(message, chat_id, parse_mode)
            if ok:
                return True

            attempt += 1
            if attempt > self.max_retries:
                break

            delay = min(
                retry_after if retry_after is not None else (2**attempt),
                self.retry_backoff_max_sec,
            )
            self.logger.warning("Telegram send retry attempt=%s delay=%ss", attempt, delay)
            await asyncio.sleep(delay)

        return False

    async def send_message(
        self, message: str, chat_id: int, parse_mode: str = "HTML"
    ) -> tuple[bool, float | None]:
        """Send one Telegram message and return status plus optional retry delay."""
        url = f"{self.base_url}sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }
        if self.session is None:
            self.logger.error("Telegram session is not initialized")
            return False, None
        try:
            response = await self.session.post(url, json=payload)
            try:
                data: Any = response.json()
            except ValueError:
                data = response.text

            if response.status_code == 200:
                return True, None
            if response.status_code == 429:
                retry_after = (
                    data.get("parameters", {}).get("retry_after")
                    if isinstance(data, dict)
                    else None
                )
                self.logger.warning("Telegram rate limited: retry_after=%s", retry_after)
                return False, float(retry_after) if retry_after is not None else None
            if response.status_code >= 500:
                self.logger.warning("Telegram transient server error: %s", response.status_code)
                return False, None

            self.logger.error(
                "Failed to send message to Telegram: %s %s", response.status_code, data
            )
            return False, None
        except Exception as exc:
            self.logger.error("Failed to send message to Telegram: %s", exc)
            return False, None

    async def stop(self) -> None:
        self.logger.info("Stopping Telegram bot...")
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        if self.session is not None:
            await self.session.aclose()
            self.session = None
        self.logger.info("Telegram bot stopped")
