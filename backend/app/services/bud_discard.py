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

"""Discard a BUD from code, with the effects of ``PATCH /buds/{id} {status: discarded}``.

The linked feature goes inactive, the timeline gets the ordinary
``status_change`` (which :mod:`app.services.bud_restore` reads to bring the
BUD back), assignment runs for ``discarded``, and the pre-discard state is
kept as a version. No agent runs for ``discarded``.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus
from app.models.bud_version import BUDEditSource
from app.repositories import bud_version as bud_version_repo
from app.services.bud_status_change import apply_status_change
from app.services.feature_lifecycle import transition_feature_for_bud

TERMINAL = (BUDStatus.CLOSED, BUDStatus.DISCARDED)


class BUDNotDiscardableError(ValueError):
    """The BUD is already closed or discarded."""


async def discard_bud(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    *,
    actor_id: uuid.UUID,
    actor_name: str | None,
) -> None:
    """Move ``bud`` to ``discarded``. The caller holds its row lock and commits.

    Raises:
        BUDNotDiscardableError: ``bud`` is closed or already discarded.
    """
    if bud.status in TERMINAL:
        raise BUDNotDiscardableError(f"BUD-{bud.bud_number} is already {bud.status.value}.")
    snapshot = bud_version_repo.build_snapshot(bud)
    old_status = bud.status
    await transition_feature_for_bud(db, org_id, bud.bud_number, BUDStatus.DISCARDED)
    await apply_status_change(
        db,
        org_id,
        bud,
        old_status,
        BUDStatus.DISCARDED,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    await bud_version_repo.commit_snapshot(
        db,
        bud_id=bud.id,
        phase=old_status,
        snapshot=snapshot,
        source=BUDEditSource.UI,
        edited_by=actor_id,
    )
    bud.status = BUDStatus.DISCARDED
    await db.flush()
