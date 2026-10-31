# Copyright 2025-2026 Arun Rajkumar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Direct messages to members on Slack, in the background.

Best effort: failures are logged and never raised, since the change that
triggered the message is already saved and visible in the app.
"""

import asyncio
import uuid
from collections.abc import Mapping

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_secret
from app.database import AsyncSessionLocal
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.services.notifications import (
    NotificationCategory,
    category_default,
    category_permission,
)
from app.services.scheduling.pace import Pace
from app.services.slack_client import chat_post_message, conversations_open

logger = structlog.get_logger(__name__)


async def bot_token(db: AsyncSession, org_id: uuid.UUID) -> str:
    """The org's Slack bot token, or "" when Slack isn't connected (or the
    saved token can't be read, which is logged: see :func:`token_unreadable`)."""
    encrypted = await OrganizationRepository(db).get_slack_bot_token(org_id)
    token = decrypt_secret(encrypted) if encrypted else ""
    if encrypted and not token:
        logger.error("slack_bot_token_unreadable", org_id=str(org_id))
    return token


async def token_unreadable(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """A token is saved but can't be decrypted (ENCRYPTION_KEY changed?)."""
    encrypted = await OrganizationRepository(db).get_slack_bot_token(org_id)
    return bool(encrypted) and not decrypt_secret(encrypted or "")


async def send_dm(
    org_id: uuid.UUID, user_ids: set[uuid.UUID], category: NotificationCategory, text: str
) -> None:
    """DM each of ``user_ids`` who hasn't muted ``category`` and may receive it."""
    async with AsyncSessionLocal() as session:
        token = await bot_token(session, org_id)
        if not token:
            return
        pairs = await _recipients(session, org_id, category, user_ids)
    await _deliver(org_id, token, [slack_id for _uid, slack_id in pairs], text)


async def send_each(
    org_id: uuid.UUID,
    category: NotificationCategory,
    texts: Mapping[uuid.UUID, str],
    *,
    pace: Pace | None = None,
) -> dict[uuid.UUID, bool]:
    """DM each person their own text; whether it reached them, per recipient.

    People who muted ``category``, can't receive it or aren't linked to
    Slack are left out of the result, as is everyone when Slack isn't
    connected. ``pace`` spaces the DMs out (one at a time without it), so a
    large batch stays inside Slack's rate limits instead of failing en masse.
    """
    async with AsyncSessionLocal() as session:
        token = await bot_token(session, org_id)
        if not token:
            return {}
        pairs = await _recipients(session, org_id, category, set(texts))
    turns = pace or Pace(1, 0.0)

    async def _one(user_id: uuid.UUID, slack_id: str) -> tuple[uuid.UUID, bool]:
        async with turns.turn():
            return user_id, await _deliver_one(org_id, token, slack_id, texts[user_id])

    return dict(await asyncio.gather(*(_one(uid, sid) for uid, sid in pairs)))


async def _recipients(
    session: AsyncSession,
    org_id: uuid.UUID,
    category: NotificationCategory,
    user_ids: set[uuid.UUID],
) -> list[tuple[uuid.UUID, str]]:
    return await UserRepository(session).list_slack_recipients(
        org_id,
        category=category,
        default_enabled=category_default(category),
        permission=category_permission(category),
        user_ids=user_ids,
    )


async def send_security_dm(org_id: uuid.UUID, user_id: uuid.UUID, text: str) -> None:
    """DM a security alert (e.g. bank details changed). It can't be muted."""
    async with AsyncSessionLocal() as session:
        token = await bot_token(session, org_id)
        if not token:
            logger.info("security_dm_not_sent", reason="no_token", user_id=str(user_id))
            return
        pairs = await UserRepository(session).list_active_slack_user_pairs(org_id)
    slack_ids = [sid for uid, sid in pairs if uid == user_id]
    if not slack_ids:
        # The in-app notice still went out; there's just no Slack copy.
        logger.info("security_dm_not_sent", reason="not_linked", user_id=str(user_id))
    await _deliver(org_id, token, slack_ids, text)


async def _deliver(org_id: uuid.UUID, token: str, slack_ids: list[str], text: str) -> None:
    for slack_id in slack_ids:
        await _deliver_one(org_id, token, slack_id, text)


async def _deliver_one(org_id: uuid.UUID, token: str, slack_id: str, text: str) -> bool:
    try:
        channel = await conversations_open(token, slack_id)
        return bool(channel) and await chat_post_message(token, channel or "", text) is not None
    except Exception:
        logger.warning("slack_dm_failed", org_id=str(org_id), exc_info=True)
        return False
