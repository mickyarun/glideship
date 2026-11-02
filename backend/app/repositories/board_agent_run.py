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

"""Data access for agent runs on cards, scoped to an organization.

A card has at most one active run (the partial unique index
``uq_board_card_agent_runs_one_active``); :meth:`claim` inserts against it
and reports a clash instead of raising, so a move into an ``on_enter``
stage never fails because a run is already going. Starting runs in one org
is serialised by :meth:`lock_starts`, so the run caps' count and the insert
can't interleave; stale and interrupted runs live in
:mod:`app.repositories.board_agent_run_sweep`.
"""

import uuid
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_agent import (
    ACTIVE_RUN_STATUSES,
    BoardAgentRunStatus,
    BoardCardAgentRun,
)
from app.models.board_card import BoardCard
from app.repositories.base import BaseRepository

# The first key of the per-org advisory lock that serialises run starts.
_START_LOCK_NAMESPACE = 0x62617267
_ACTIVE_WHERE = text("status IN (" + ", ".join(f"'{s.value}'" for s in ACTIVE_RUN_STATUSES) + ")")


class BoardCardAgentRunRepository(BaseRepository[BoardCardAgentRun]):
    """Tenant-scoped repository for card agent runs."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardAgentRun, db, org_id=org_id)

    async def claim(self, values: dict[str, Any]) -> BoardCardAgentRun | None:
        """Insert a pending run, or None when the card already has an active one."""
        run_id = uuid.uuid4()
        attempt = await self._next_attempt(values["card_id"], values.get("stage_agent_id"))
        stmt = (
            insert(BoardCardAgentRun)
            .values(
                id=run_id,
                org_id=self._org_id,
                status=BoardAgentRunStatus.PENDING,
                attempt=attempt,
                **values,
            )
            .on_conflict_do_nothing(index_elements=["card_id"], index_where=_ACTIVE_WHERE)
            .returning(BoardCardAgentRun.id)
        )
        if (await self._db.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.get_by_id(run_id)

    async def _next_attempt(self, card_id: uuid.UUID, stage_agent_id: uuid.UUID | None) -> int:
        """One more than the runs this agent already made on the card."""
        stmt = self._scoped(
            select(func.count())
            .select_from(BoardCardAgentRun)
            .where(
                BoardCardAgentRun.card_id == card_id,
                BoardCardAgentRun.stage_agent_id == stage_agent_id,
            )
        )
        return int((await self._db.execute(stmt)).scalar_one()) + 1

    async def get_for_card(
        self, card_id: uuid.UUID, run_id: uuid.UUID
    ) -> BoardCardAgentRun | None:
        """One of the card's runs."""
        stmt = self._scoped(
            select(BoardCardAgentRun).where(
                BoardCardAgentRun.id == run_id, BoardCardAgentRun.card_id == card_id
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def active_for_card(self, card_id: uuid.UUID) -> BoardCardAgentRun | None:
        """The card's pending or running run, if it has one."""
        stmt = self._scoped(
            select(BoardCardAgentRun).where(
                BoardCardAgentRun.card_id == card_id,
                BoardCardAgentRun.status.in_(ACTIVE_RUN_STATUSES),
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def count_active(self, *, triggered_by: uuid.UUID | None = None) -> int:
        """Pending and running runs in the org, or only those ``triggered_by`` started."""
        stmt = (
            select(func.count())
            .select_from(BoardCardAgentRun)
            .where(BoardCardAgentRun.status.in_(ACTIVE_RUN_STATUSES))
        )
        if triggered_by is not None:
            stmt = stmt.where(BoardCardAgentRun.triggered_by == triggered_by)
        return int((await self._db.execute(self._scoped(stmt))).scalar_one())

    async def active_ids_on_board(self, board_id: uuid.UUID) -> list[uuid.UUID]:
        """The ids of the board's cards' pending and running runs (not locked)."""
        stmt = (
            select(BoardCardAgentRun.id)
            .join(BoardCard, BoardCard.id == BoardCardAgentRun.card_id)
            .where(
                BoardCardAgentRun.org_id == self._org_id,
                BoardCard.board_id == board_id,
                BoardCardAgentRun.status.in_(ACTIVE_RUN_STATUSES),
            )
            .order_by(BoardCardAgentRun.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def recent_for_card(self, card_id: uuid.UUID, limit: int) -> list[BoardCardAgentRun]:
        """The card's latest runs, newest first."""
        stmt = self._scoped(
            select(BoardCardAgentRun)
            .where(BoardCardAgentRun.card_id == card_id)
            .order_by(BoardCardAgentRun.created_at.desc(), BoardCardAgentRun.id.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def lock(self, run: BoardCardAgentRun) -> None:
        """Hold the run's row until the transaction ends, and re-read it."""
        await self._db.refresh(run, with_for_update=True)

    async def lock_starts(self) -> None:
        """Hold the org's run-start lock until the transaction ends.

        Taken before counting active runs for the caps and claiming one, so
        two starts at the edge of a cap can't both pass. Callers that also
        lock the card take the card first.
        """
        key = func.hashtext(str(self._org_id))
        await self._db.execute(select(func.pg_advisory_xact_lock(_START_LOCK_NAMESPACE, key)))

    async def mark_running(self, run: BoardCardAgentRun) -> bool:
        """Move a pending run to running, stamping when; False when it isn't pending any more.

        The row is re-read either way.
        """
        stmt = (
            update(BoardCardAgentRun)
            .where(
                BoardCardAgentRun.id == run.id,
                BoardCardAgentRun.org_id == self._org_id,
                BoardCardAgentRun.status == BoardAgentRunStatus.PENDING,
            )
            .values(status=BoardAgentRunStatus.RUNNING, started_at=func.now())
            .returning(BoardCardAgentRun.id)
            .execution_options(synchronize_session=False)
        )
        started = (await self._db.execute(stmt)).scalar_one_or_none() is not None
        await self._db.refresh(run)
        return started
