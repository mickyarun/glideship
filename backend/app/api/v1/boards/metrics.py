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


"""Board metrics: one board's, and a summary across the boards I can open."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards import _access as can
from app.core.board_deps import board_caller
from app.core.deps import get_db
from app.schemas.boards.metrics import BoardMetrics, BoardMetricsSummary
from app.services.boards import metrics
from app.services.boards.access import BoardAccess, BoardCaller

router = APIRouter(tags=["boards"])


@router.get("/metrics/summary", response_model=BoardMetricsSummary)
async def metrics_summary(
    caller: BoardCaller = Depends(board_caller), db: AsyncSession = Depends(get_db)
) -> BoardMetricsSummary:
    """Throughput, cycle time, WIP, aging and lead time for every active board I can open."""
    return await metrics.metrics_summary(db, caller)


@router.get("/{key}/metrics", response_model=BoardMetrics)
async def board_metrics(
    access: BoardAccess = Depends(can.view_board), db: AsyncSession = Depends(get_db)
) -> BoardMetrics:
    """One board's metrics, with its oldest aging cards."""
    return await metrics.board_metrics(db, access)
