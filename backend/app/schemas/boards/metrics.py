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


"""Board metrics: throughput, cycle time, WIP, aging and idea-to-prod lead time."""

from datetime import date, datetime

from pydantic import BaseModel

from app.models.board_enums import BoardStageCategory


class WeekCount(BaseModel):
    """Cards done in the UTC week starting ``week_start`` (a Monday).

    Each card counts once, in the week of its latest entry into a done stage
    within the chart, so a card sent back and done again isn't counted twice.
    """

    week_start: date
    count: int


class DurationStats(BaseModel):
    """How many durations were measured, and their median and 85th percentile in hours."""

    count: int
    median_hours: float | None
    p85_hours: float | None


class AgingCard(BaseModel):
    """An open card in progress now; ``since`` is when it first entered ``in_progress``."""

    key: str
    title: str
    since: datetime


class FlowMetrics(BaseModel):
    """One board's numbers.

    ``throughput`` has one entry per week of the throughput chart, oldest
    first. ``cycle_time`` and ``lead_time`` cover the metrics window.
    ``wip`` counts open cards by their current category, every category
    listed.
    """

    throughput: list[WeekCount]
    cycle_time: DurationStats
    lead_time: DurationStats
    wip: dict[BoardStageCategory, int]
    aging_count: int


class MetricsWindow(BaseModel):
    """The look-backs every number used."""

    window_days: int
    weeks: int
    aging_days: int


class BoardMetrics(FlowMetrics):
    """One board's metrics, with its oldest aging cards."""

    window: MetricsWindow
    aging: list[AgingCard]


class BoardMetricsRow(FlowMetrics):
    """One board in the cross-board summary."""

    key: str
    name: str


class BoardMetricsSummary(BaseModel):
    """The same numbers for every active board the caller can open, by name."""

    window: MetricsWindow
    boards: list[BoardMetricsRow]
