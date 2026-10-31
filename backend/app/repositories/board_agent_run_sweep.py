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

"""Card runs that can no longer be going: interrupted by a restart, or stale.

A run is stale once it has been pending (since it was created) or running
(since it started) for longer than its deadline plus a grace: its skill's
``timeout_seconds``, else the boards default. Its job is either gone or hung.
Stale runs are failed with :data:`STALE` in one ``UPDATE … RETURNING``, by
the periodic sweep (every org) and when a new run is claimed on the card.
These statements read across orgs only where the docstring says so.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_skill import AgentSkill
from app.models.board_agent import (
    ACTIVE_RUN_STATUSES,
    BoardAgentRunStatus,
    BoardCardAgentRun,
)
from app.models.board_card import BoardCard
from app.repositories.base import rowcount

INTERRUPTED = "The server restarted while this run was going. Run it again."
STALE = "This run went past its deadline without finishing, so it was stopped. Run it again."


def _stale(timeout_seconds: int, grace_seconds: int) -> ColumnElement[bool]:
    """Active, and older than its skill's deadline (else ``timeout_seconds``) plus the grace."""
    skill_timeout = (
        select(func.nullif(AgentSkill.timeout_seconds, 0))
        .where(AgentSkill.id == BoardCardAgentRun.skill_id)
        .correlate(BoardCardAgentRun)
        .scalar_subquery()
    )
    allowed = func.coalesce(skill_timeout, timeout_seconds) + grace_seconds
    since = func.coalesce(BoardCardAgentRun.started_at, BoardCardAgentRun.created_at)
    return and_(
        BoardCardAgentRun.status.in_(ACTIVE_RUN_STATUSES),
        since < func.now() - func.make_interval(0, 0, 0, 0, 0, 0, allowed),
    )


async def fail_stale_runs(
    db: AsyncSession,
    *,
    timeout_seconds: int,
    grace_seconds: int,
    org_id: uuid.UUID | None = None,
    card_id: uuid.UUID | None = None,
) -> list[tuple[BoardCardAgentRun, uuid.UUID]]:
    """Fail stale runs; each with its card's board id. Every org when ``org_id`` is None."""
    stmt = (
        update(BoardCardAgentRun)
        .where(BoardCard.id == BoardCardAgentRun.card_id, _stale(timeout_seconds, grace_seconds))
        .values(status=BoardAgentRunStatus.FAILED, error_message=STALE, finished_at=func.now())
        .returning(BoardCardAgentRun, BoardCard.board_id)
        .execution_options(synchronize_session=False)
    )
    if org_id is not None:
        stmt = stmt.where(BoardCardAgentRun.org_id == org_id)
    if card_id is not None:
        stmt = stmt.where(BoardCardAgentRun.card_id == card_id)
    return [(run, board_id) for run, board_id in (await db.execute(stmt)).all()]


async def recover_stuck_board_agent_runs(db: AsyncSession) -> int:
    """Mark runs a restart left pending or running as failed; returns how many.

    Startup-only and cross-org: the in-memory jobs behind them are gone.
    """
    stmt = (
        update(BoardCardAgentRun)
        .where(BoardCardAgentRun.status.in_(ACTIVE_RUN_STATUSES))
        .values(
            status=BoardAgentRunStatus.FAILED,
            error_message=INTERRUPTED,
            finished_at=datetime.now(UTC),
        )
    )
    return rowcount(await db.execute(stmt))
