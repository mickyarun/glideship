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

"""Queue socket access re-checks for after the commit.

Call these from any write that can take board access away from someone:
a board member or team removed, a role lowered, a board hidden, someone
leaving a team, a team archived, an org role or its permissions changed,
a member deactivated, offboarded or merged away. The sockets re-check against the
committed state, using the permissions in the database at that moment.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.organization import OrganizationRepository
from app.services.after_commit import publish_after_commit
from app.services.ws_topic_policy import access_topic, people_access_topic


def _ids(user_ids: Iterable[uuid.UUID] | None) -> list[str] | None:
    return None if user_ids is None else sorted({str(u) for u in user_ids})


def recheck_topic(db: AsyncSession, topic: str, user_ids: Iterable[uuid.UUID] | None) -> None:
    """Re-check ``topic`` for these people (``None``: everyone holding it)."""
    control = access_topic(topic)
    if control is not None:
        publish_after_commit(db, control, {"user_ids": _ids(user_ids)})


def recheck_people(
    db: AsyncSession, org_id: uuid.UUID, user_ids: Iterable[uuid.UUID] | None
) -> None:
    """Re-check every revocable topic these people hold (``None``: everyone in the org)."""
    ids = _ids(user_ids)
    if ids == []:
        return
    publish_after_commit(db, people_access_topic(str(org_id)), {"user_ids": ids})


async def recheck_account(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Re-check someone's topics in every org they belong to.

    Use it when the account itself changes (deactivated, offboarded,
    merged away): ``User.is_active`` holds in every org, not just the
    caller's.
    """
    for org_id in await OrganizationRepository(db).ids_for_member(user_id):
        recheck_people(db, org_id, {user_id})
