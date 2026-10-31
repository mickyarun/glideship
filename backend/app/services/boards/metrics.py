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


"""Board metrics, for one board or every board the caller can open.

Each number is one query covering all the boards asked about
(:mod:`app.repositories.board_metrics`,
:mod:`app.repositories.board_metrics_durations`), so the summary costs the
same handful of queries however many boards there are. Look-backs come
from ``BoardsConfig``: ``metrics_window_days``, ``metrics_throughput_weeks``,
``aging_days`` and ``metrics_aging_list_limit``.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_enums import BoardStageCategory
from app.repositories.board_metrics import BoardMetricsRepository, MetricsBoard
from app.repositories.board_metrics_durations import BoardDurationRepository, DurationRow
from app.schemas.boards.metrics import (
    AgingCard,
    BoardMetrics,
    BoardMetricsRow,
    BoardMetricsSummary,
    DurationStats,
    FlowMetrics,
    MetricsWindow,
    WeekCount,
)
from app.services.boards.access import BoardAccess, BoardCaller
from app.services.boards.reads import card_key

_SECONDS_PER_HOUR = 3600
_HOURS_DECIMALS = 1
_EMPTY = DurationRow(0, None, None)


@dataclass(frozen=True)
class _Window:
    weeks: list[date]
    week_since: datetime
    since: datetime
    aging_before: datetime

    @classmethod
    def now(cls) -> "_Window":
        now = datetime.now(UTC)
        boards = settings.boards
        this_week = now.date() - timedelta(days=now.weekday())
        weeks = [
            this_week - timedelta(weeks=n)
            for n in reversed(range(boards.metrics_throughput_weeks))
        ]
        return cls(
            weeks=weeks,
            week_since=datetime.combine(weeks[0], datetime.min.time(), tzinfo=UTC),
            since=now - timedelta(days=boards.metrics_window_days),
            aging_before=now - timedelta(days=boards.aging_days),
        )

    @staticmethod
    def read() -> MetricsWindow:
        boards = settings.boards
        return MetricsWindow(
            window_days=boards.metrics_window_days,
            weeks=boards.metrics_throughput_weeks,
            aging_days=boards.aging_days,
        )


@dataclass(frozen=True)
class _Numbers:
    throughput: dict[uuid.UUID, dict[date, int]]
    cycle: dict[uuid.UUID, DurationRow]
    lead: dict[uuid.UUID, DurationRow]
    wip: dict[uuid.UUID, dict[BoardStageCategory, int]]
    aging: dict[uuid.UUID, int]

    def flow(self, board_id: uuid.UUID, window: _Window) -> FlowMetrics:
        weekly = self.throughput.get(board_id, {})
        wip = self.wip.get(board_id, {})
        return FlowMetrics(
            throughput=[WeekCount(week_start=w, count=weekly.get(w, 0)) for w in window.weeks],
            cycle_time=_hours(self.cycle.get(board_id, _EMPTY)),
            lead_time=_hours(self.lead.get(board_id, _EMPTY)),
            wip={category: wip.get(category, 0) for category in BoardStageCategory},
            aging_count=self.aging.get(board_id, 0),
        )


def _hours(row: DurationRow) -> DurationStats:
    def h(seconds: float | None) -> float | None:
        return None if seconds is None else round(seconds / _SECONDS_PER_HOUR, _HOURS_DECIMALS)

    return DurationStats(
        count=row.count, median_hours=h(row.median_seconds), p85_hours=h(row.p85_seconds)
    )


async def _numbers(
    db: AsyncSession, org_id: uuid.UUID, board_ids: list[uuid.UUID], window: _Window
) -> _Numbers:
    flow = BoardMetricsRepository(db, org_id=org_id)
    durations = BoardDurationRepository(db, org_id=org_id)
    return _Numbers(
        throughput=await flow.throughput(board_ids, window.week_since),
        cycle=await durations.cycle_times(board_ids, window.since),
        lead=await durations.lead_times(board_ids, window.since),
        wip=await flow.wip(board_ids),
        aging=await flow.aging_counts(board_ids, window.aging_before),
    )


async def board_metrics(db: AsyncSession, access: BoardAccess) -> BoardMetrics:
    """The board's metrics and its oldest aging cards."""
    board, window = access.board, _Window.now()
    numbers = await _numbers(db, access.org_id, [board.id], window)
    oldest = await BoardMetricsRepository(db, org_id=access.org_id).oldest_aging(
        board.id, window.aging_before, settings.boards.metrics_aging_list_limit
    )
    return BoardMetrics(
        **numbers.flow(board.id, window).model_dump(),
        window=_Window.read(),
        aging=[
            AgingCard(key=card_key(board.key, row.number), title=row.title, since=row.since)
            for row in oldest
        ],
    )


async def metrics_summary(db: AsyncSession, caller: BoardCaller) -> BoardMetricsSummary:
    """The same numbers for every active board the caller can open."""
    repo = BoardMetricsRepository(db, org_id=caller.org_id)
    boards: list[MetricsBoard] = await repo.visible_boards(caller.user_id, caller.perms)
    window = _Window.now()
    rows: list[BoardMetricsRow] = []
    if boards:
        numbers = await _numbers(db, caller.org_id, [b.id for b in boards], window)
        rows = [
            BoardMetricsRow(**numbers.flow(b.id, window).model_dump(), key=b.key, name=b.name)
            for b in boards
        ]
    return BoardMetricsSummary(window=_Window.read(), boards=rows)
