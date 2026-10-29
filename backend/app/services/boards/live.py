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

"""Live updates on ``board:<board_id>``, published only after the commit.

A service collects what changed in a :class:`BoardChanges` and calls
:meth:`BoardChanges.commit`, so a client never hears about a row it can't
read yet, and a rolled-back change is never announced.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import event_bus
from app.services.ws_topic_policy import access_topic


class BoardSocketEvent(StrEnum):
    """Event names on a board topic; the frontend mirrors them as a union."""

    BOARD_UPDATED = "board_updated"
    CARD_CREATED = "card_created"
    CARD_UPDATED = "card_updated"
    CARD_MOVED = "card_moved"
    CARD_ARCHIVED = "card_archived"
    CARD_RESTORED = "card_restored"
    CARD_ACTIVITY = "card_activity"
    DOC_UPDATED = "doc_updated"
    STAGE_CHANGED = "stage_changed"
    STAGE_REORDERED = "stage_reordered"
    LABEL_CHANGED = "label_changed"
    MEMBER_CHANGED = "member_changed"


def board_topic(board_id: uuid.UUID) -> str:
    """The socket topic for one board."""
    return f"board:{board_id}"


@dataclass
class BoardChanges:
    """What one request changed on a board, announced after it commits.

    ``recheck`` names the people whose board subscriptions must be checked
    again; ``None`` in it means everyone subscribed.
    """

    board_id: uuid.UUID
    events: list[tuple[BoardSocketEvent, dict[str, Any]]] = field(default_factory=list)
    recheck: set[uuid.UUID] | None = field(default_factory=set)

    def emit(self, event: BoardSocketEvent, **payload: Any) -> None:
        """Queue one event for after the commit."""
        self.events.append((event, payload))

    def recheck_access(self, user_ids: set[uuid.UUID] | None) -> None:
        """Queue a re-check of these people's subscriptions (``None``: everyone's)."""
        if user_ids is None or self.recheck is None:
            self.recheck = None
        else:
            self.recheck |= user_ids

    async def commit(self, db: AsyncSession) -> None:
        """Commit the session, then publish everything queued."""
        await db.commit()
        topic = board_topic(self.board_id)
        for event, payload in self.events:
            event_bus.publish(topic, {"event": event.value, **payload})
        control = access_topic(topic)
        if control is not None and self.recheck != set():
            users = None if self.recheck is None else sorted(str(u) for u in self.recheck)
            event_bus.publish(control, {"user_ids": users})
