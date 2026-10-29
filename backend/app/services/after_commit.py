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

"""Publish on the event bus only once the session's transaction commits.

Writers queue a message on their session with :func:`publish_after_commit`;
a session ``after_commit`` hook sends everything queued, in order, and a
rollback throws it away. So a client never hears about a row it can't read
yet, and a change that failed is never announced, whichever code path
commits the session.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from app.services import event_bus

_PENDING = "publish_after_commit"


def publish_after_commit(db: AsyncSession, topic: str, data: dict[str, Any]) -> None:
    """Send ``data`` on ``topic`` when ``db``'s transaction commits."""
    db.sync_session.info.setdefault(_PENDING, []).append((topic, data))


@event.listens_for(Session, "after_commit")
def _send(session: Session) -> None:
    for topic, data in session.info.pop(_PENDING, []):
        event_bus.publish(topic, data)


@event.listens_for(Session, "after_transaction_end")
def _discard(session: Session, transaction: SessionTransaction) -> None:
    # A commit has already sent and cleared the queue; anything left when
    # the outermost transaction ends was rolled back. Savepoints have a
    # parent, so one rolled back mid-request leaves the queue alone.
    if transaction.parent is None:
        session.info.pop(_PENDING, None)
