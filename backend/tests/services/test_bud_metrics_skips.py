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


"""Learning metrics don't score the BUD phases a board handover skipped."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.repositories.bud_estimate import BUDEstimateSnapshotRepository
from app.repositories.bud_timeline import BUDTimelineRepository
from app.services.bud_metrics_phases import build_phase_metrics
from app.services.bud_metrics_skips import skipped_by_handover

T0 = datetime(2026, 10, 1, tzinfo=UTC)
# The phases learning metrics score (a discarded BUD's status isn't one).
SCORED = {"bud", "design", "tech_arch", "development"}


def test_the_phases_a_handover_left_are_skipped() -> None:
    events = [("design", T0, True), ("tech_arch", T0, True), ("development", T0, False)]
    assert skipped_by_handover(events) == {"bud", "design"}


def test_a_handover_again_keeps_the_phases_worked_on_the_first_pass() -> None:
    """First landed at design and worked there; sent back; handed over again to development.

    The second walk steps through bud and design again, but design had real
    work (it was left by hand the first time), so only bud is skipped.
    """
    events = [
        ("design", T0, True),
        ("tech_arch", T0 + timedelta(days=5), False),
        ("discarded", T0 + timedelta(days=6), False),
        ("bud", T0 + timedelta(days=7), True),
        ("design", T0 + timedelta(days=7), True),
        ("tech_arch", T0 + timedelta(days=7), True),
        ("development", T0 + timedelta(days=7), True),
    ]
    assert skipped_by_handover(events) & SCORED == {"bud"}


def test_a_handover_again_still_skips_what_both_walks_skipped() -> None:
    """Landed at development twice: bud, design and tech_arch never had any time."""
    events = [
        ("design", T0, True),
        ("tech_arch", T0, True),
        ("development", T0, True),
        ("discarded", T0 + timedelta(days=3), False),
        ("bud", T0 + timedelta(days=4), True),
        ("design", T0 + timedelta(days=4), True),
        ("tech_arch", T0 + timedelta(days=4), True),
        ("development", T0 + timedelta(days=4), True),
    ]
    assert skipped_by_handover(events) & SCORED == {"bud", "design", "tech_arch"}


def test_a_bud_moved_by_hand_skips_nothing() -> None:
    events = [("design", T0, False), ("design", T0, True), ("tech_arch", T0, False)]
    assert skipped_by_handover(events) == set()


async def test_skipped_phases_report_no_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    landed = T0 + timedelta(minutes=1)
    rows = [
        SimpleNamespace(
            detail={"from": "bud", "to": "design", "via": "handover"}, created_at=landed
        ),
        SimpleNamespace(
            detail={"from": "design", "to": "tech_arch", "via": "handover"}, created_at=landed
        ),
        SimpleNamespace(
            detail={"from": "tech_arch", "to": "development"},
            created_at=landed + timedelta(days=2),
        ),
    ]
    estimates = {p: {"expected_days": 1.0} for p in ("bud", "design", "tech_arch", "development")}

    async def _events(self: Any, bud_id: uuid.UUID, event_type: str) -> list[Any]:
        return rows

    async def _earliest(self: Any, bud_id: uuid.UUID) -> Any:
        return SimpleNamespace(phase_estimates=estimates)

    monkeypatch.setattr(BUDTimelineRepository, "list_for_bud_by_event_type", _events)
    monkeypatch.setattr(BUDEstimateSnapshotRepository, "get_earliest_for_bud", _earliest)
    bud = SimpleNamespace(id=uuid.uuid4(), created_at=T0)

    out = await build_phase_metrics(
        None,  # type: ignore[arg-type]
        uuid.uuid4(),
        bud,  # type: ignore[arg-type]
        landed + timedelta(days=5),
    )

    assert out["bud"]["drift_pct"] is None and out["bud"]["skipped_at_handover"] is True
    assert out["design"]["drift_pct"] is None and out["design"]["actual_days"] == 0.0
    # Where it landed is real work: tech_arch took 2 days against 1 estimated.
    assert out["tech_arch"]["drift_pct"] == 100.0
    assert out["tech_arch"]["skipped_at_handover"] is False
    assert out["development"]["drift_pct"] == 200.0
