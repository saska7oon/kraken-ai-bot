"""
Discord notifier
================

Sends plain-language messages to a Discord channel via webhook.

The webhook URL is read from the ``discord_webhook`` Docker Swarm secret. It is
never passed through an environment variable and never logged.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Discord rejects message content longer than 2000 characters.
MAX_CONTENT = 1900


class DiscordNotifier:
    """Minimal async Discord webhook client."""

    def __init__(
        self,
        secret_path: str = "/run/secrets/discord_webhook",
        timeout: int = 15,
    ):
        self.secret_path = secret_path
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._webhook_url: Optional[str] = None

    @property
    def configured(self) -> bool:
        """True when a non-empty webhook URL is available."""
        return bool(self._read_webhook())

    def _read_webhook(self) -> str:
        if self._webhook_url is None:
            try:
                with open(self.secret_path, "r") as f:
                    self._webhook_url = f.read().strip()
            except OSError:
                # Missing secret is a normal, non-fatal configuration state.
                self._webhook_url = ""
        return self._webhook_url

    async def send(self, content: str) -> bool:
        """
        Send a message. Returns True on success.

        Failures are logged but never raised: a notification problem must not
        affect trading or crash a plugin run.
        """
        url = self._read_webhook()
        if not url:
            logger.debug("Discord webhook not configured; skipping notification")
            return False

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)

        ok = True
        for chunk in _chunk(content, MAX_CONTENT):
            try:
                async with self._session.post(url, json={"content": chunk}) as response:
                    if response.status >= 300:
                        body = await response.text()
                        logger.warning(
                            "Discord webhook returned %s: %s", response.status, body[:200]
                        )
                        ok = False
            except aiohttp.ClientError as e:
                logger.warning("Discord notification failed: %s", e)
                ok = False
        return ok

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None


def _chunk(text: str, size: int) -> list[str]:
    """Split text into chunks at line boundaries where possible."""
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        # A single line longer than the limit must be hard-split.
        while len(line) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


# Convenience for callers that only need a path-based check.
def webhook_secret_exists(path: str = "/run/secrets/discord_webhook") -> bool:
    return os.path.exists(path)
