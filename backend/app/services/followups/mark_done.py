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

"""The "Mark done" button in a follow-ups DM: tick the card's due date done.

The click is signed by Slack for the org (checked by the endpoint). The
person is looked up by their Slack id and needs the same board role as
ticking it in the app; then the button becomes a "Done" mark. Problems
are told to them alone, in an ephemeral message.
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_deps import member_permission_set
from app.models.organization import Organization
from app.repositories.user import UserRepository
from app.schemas.boards.card import CardUpdate
from app.services.boards.access import BoardForbiddenError, resolve_card_by_key
from app.services.boards.card_edit import update_card
from app.services.boards.constants import BoardAction
from app.services.boards.errors import BoardError
from app.services.followups.compose import MARK_DONE_ACTION
from app.services.followups.done_blocks import marked_done
from app.services.slack_dm import bot_token
from app.services.slack_interactive import post_ephemeral, update_message

logger = structlog.get_logger(__name__)

NOT_LINKED = "Your Slack account isn't linked to an active Glideship account here."


def is_mark_done(payload: dict[str, Any]) -> bool:
    """Whether a Slack interaction is a follow-ups "Mark done" click."""
    action = (payload.get("actions") or [{}])[0]
    return payload.get("type") == "block_actions" and action.get("action_id") == MARK_DONE_ACTION


async def handle_mark_done(db: AsyncSession, org: Organization, payload: dict[str, Any]) -> None:
    """Tick the clicked card's due date done and mark it so in the message."""
    key = str((payload.get("actions") or [{}])[0].get("value") or "")
    slack_user = str((payload.get("user") or {}).get("id") or "")
    channel = str((payload.get("channel") or {}).get("id") or "")
    token = await bot_token(db, org.id)
    if not key or not token:
        return
    found = await UserRepository(db).get_active_by_slack_id_with_role(org.id, slack_user)
    perms = await member_permission_set(db, found[0].id, org.id) if found else None
    if found is None or perms is None:
        await post_ephemeral(token, channel, slack_user, NOT_LINKED)
        return
    try:
        target = await resolve_card_by_key(
            db, user_id=found[0].id, org_id=org.id, perms=perms, key=key
        )
        if not target.access.may(BoardAction.EDIT_CARD):
            raise BoardForbiddenError()
        if not target.card.due_done:
            await update_card(db, target, CardUpdate(due_done=True))
    except BoardError:
        logger.info("followups_mark_done_refused", org_id=str(org.id), key=key)
        problem = f"Couldn't mark {key} done: it's closed, or you can no longer edit it."
        await post_ephemeral(token, channel, slack_user, problem)
        return
    message = payload.get("message") or {}
    ts = str((payload.get("container") or {}).get("message_ts") or message.get("ts") or "")
    blocks = marked_done(list(message.get("blocks") or []), key)
    await update_message(token, channel, ts, str(message.get("text") or ""), blocks)
