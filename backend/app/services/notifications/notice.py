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

"""In-app notifications and Slack DMs staged in a transaction, sent once it commits.

Two steps around the caller's commit: :func:`stage_notice` adds the in-app
rows to the caller's transaction and returns a :class:`Notice`; the caller
commits, then calls :meth:`Notice.send` to push the rows over the websocket
and DM on Slack. Nobody hears about a change that rolled back, and a pushed
notification id always exists in the database.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.services.background import spawn
from app.services.event_bus import publish
from app.services.notifications.categories import NotificationCategory
from app.services.slack_dm import send_dm

SocketEvent = tuple[str, dict[str, Any]]


def escape_mrkdwn(text: str) -> str:
    """Escape Slack's control characters so names and titles can't inject links."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Notice:
    """Notifications staged in a transaction, to send once it commits."""

    org_id: uuid.UUID
    user_ids: set[uuid.UUID]
    category: NotificationCategory
    slack_text: str
    events: list[SocketEvent] = field(default_factory=list)

    def send(self) -> None:
        """Push the in-app rows and start the Slack messages. Call after commit."""
        for topic, payload in self.events:
            publish(topic, payload)
        if self.user_ids:
            spawn(send_dm(self.org_id, self.user_ids, self.category, self.slack_text))


def add_notification_rows(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_ids: set[uuid.UUID],
    kind: NotificationType,
    title: str,
    message: str,
    link: str,
) -> list[SocketEvent]:
    """Add one in-app row per person; the socket events to push after commit."""
    events: list[SocketEvent] = []
    for user_id in sorted(user_ids):
        note = Notification(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            type=kind,
            title=title,
            message=message,
            deep_link=link,
        )
        db.add(note)
        events.append(
            (
                f"notifications:{user_id}",
                {
                    "id": str(note.id),
                    "type": kind.value,
                    "title": title,
                    "message": message,
                    "deepLink": link,
                    "isRead": False,
                    "isDismissed": False,
                    "createdAt": datetime.now(UTC).isoformat(),
                },
            )
        )
    return events


def stage_notice(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_ids: set[uuid.UUID],
    kind: NotificationType,
    category: NotificationCategory,
    title: str,
    message: str,
    link: str,
    slack_text: str,
) -> Notice:
    """In-app rows for ``user_ids`` in the caller's transaction, and the DM to send after."""
    events = add_notification_rows(
        db, org_id=org_id, user_ids=user_ids, kind=kind, title=title, message=message, link=link
    )
    return Notice(
        org_id=org_id,
        user_ids=set(user_ids),
        category=category,
        slack_text=slack_text,
        events=events,
    )
