"""Ably realtime integration (chat + notifications).

The server holds the Ably API key and mints short-lived, capability-scoped token
requests for browsers; it also publishes events server-side. ably-python is
async, so sync Django/Celery code drives it through ``asyncio.run``. Everything
degrades gracefully when ``ABLY_API_KEY`` is unset (``is_enabled()`` is False).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

STAFF_NOTIFICATIONS_CHANNEL = "staff-notifications"


def is_enabled() -> bool:
    return bool(getattr(settings, "ABLY_API_KEY", ""))


def tender_channel(tender_public_id: str) -> str:
    return f"tender:{tender_public_id}"


def _token_request_to_dict(token_request: Any) -> dict[str, Any]:
    if hasattr(token_request, "to_dict"):
        return token_request.to_dict()
    # Fallback for SDK versions without to_dict().
    return {
        "keyName": token_request.key_name,
        "ttl": token_request.ttl,
        "capability": token_request.capability,
        "clientId": token_request.client_id,
        "timestamp": token_request.timestamp,
        "nonce": token_request.nonce,
        "mac": token_request.mac,
    }


async def _acreate_token_request(client_id: str) -> dict[str, Any]:
    from ably import AblyRest

    rest = AblyRest(settings.ABLY_API_KEY)
    try:
        token_request = await rest.auth.create_token_request(
            {
                "client_id": client_id or None,
                "capability": {
                    # Staff may read/write any tender channel and read notifications.
                    "tender:*": ["subscribe", "publish", "presence"],
                    STAFF_NOTIFICATIONS_CHANNEL: ["subscribe"],
                },
            }
        )
        return _token_request_to_dict(token_request)
    finally:
        await rest.close()


def create_token_request(client_id: str) -> dict[str, Any]:
    return asyncio.run(_acreate_token_request(client_id))


async def _apublish(channel: str, name: str, data: Any) -> None:
    from ably import AblyRest

    rest = AblyRest(settings.ABLY_API_KEY)
    try:
        await rest.channels.get(channel).publish(name, data)
    finally:
        await rest.close()


def publish(channel: str, name: str, data: Any) -> None:
    """Synchronous publish helper (call from a Celery task, never a request)."""
    if not is_enabled():
        return
    asyncio.run(_apublish(channel, name, data))
