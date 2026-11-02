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

"""Midpoint positions, the stage rules and a card's started/completed stamps."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.models.board_card import BoardCard
from app.models.board_enums import BoardStageCategory
from app.services.boards.card_timing import enter_category
from app.services.boards.errors import BoardRuleError
from app.services.boards.positions import position_between
from app.services.boards.stage_rules import check_stages

GAP = settings.boards.position_gap
TODO, DOING = BoardStageCategory.TODO, BoardStageCategory.IN_PROGRESS
DONE, CANCELED = BoardStageCategory.DONE, BoardStageCategory.CANCELED


def test_positions_split_neighbours_or_extend_the_ends() -> None:
    assert position_between(None, None) == GAP
    assert position_between(10.0, None) == 10.0 + GAP
    assert position_between(None, 10.0) == 10.0 - GAP
    assert position_between(10.0, 20.0) == 15.0


def test_neighbours_too_close_to_split_ask_for_a_rebalance() -> None:
    epsilon = settings.boards.position_epsilon
    assert position_between(1.0, 1.0 + epsilon / 2) is None
    assert position_between(1.0, 1.0) is None


@dataclass
class _Stage:
    category: BoardStageCategory
    is_default: bool = False
    id: uuid.UUID = uuid.UUID(int=0)

    def __post_init__(self) -> None:
        self.id = uuid.uuid4()


def _check(stages: list[_Stage], **kw: uuid.UUID | None) -> None:
    check_stages(
        stages,
        handover_stage_id=kw.get("handover"),
        return_stage_id=kw.get("ret"),
    )


def test_a_valid_stage_set_passes() -> None:
    stages = [_Stage(TODO, is_default=True), _Stage(DOING), _Stage(DONE)]
    _check(stages, handover=stages[2].id, ret=stages[0].id)


@pytest.mark.parametrize(
    ("stages", "message"),
    [
        ([_Stage(DONE, is_default=True)], "todo"),
        ([_Stage(TODO, is_default=True)], "done"),
        ([_Stage(TODO), _Stage(DONE)], "Exactly one"),
        ([_Stage(TODO, is_default=True), _Stage(DONE, is_default=True)], "Exactly one"),
    ],
)
def test_broken_stage_sets_are_refused(stages: list[_Stage], message: str) -> None:
    with pytest.raises(BoardRuleError, match=message):
        _check(stages)


def test_handover_stages_keep_their_categories() -> None:
    stages = [_Stage(TODO, is_default=True), _Stage(DONE)]
    with pytest.raises(BoardRuleError, match="handover stage must be a done"):
        _check(stages, handover=stages[0].id)
    with pytest.raises(BoardRuleError, match="return stage must be a todo"):
        _check(stages, handover=stages[1].id, ret=stages[1].id)
    with pytest.raises(BoardRuleError, match="one of this board"):
        _check(stages, handover=uuid.uuid4())


def test_too_many_stages_are_refused() -> None:
    limit = settings.boards.max_stages_per_board
    stages = [_Stage(TODO, is_default=True), _Stage(DONE)] + [_Stage(DOING) for _ in range(limit)]
    with pytest.raises(BoardRuleError, match="at most"):
        _check(stages)


def test_started_is_the_first_in_progress_and_completed_clears_on_reopen() -> None:
    card = BoardCard()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    enter_category(card, TODO, t0)
    assert (card.started_at, card.completed_at) == (None, None)
    enter_category(card, DOING, t0 + timedelta(days=1))
    enter_category(card, TODO, t0 + timedelta(days=2))
    enter_category(card, DOING, t0 + timedelta(days=3))
    assert card.started_at == t0 + timedelta(days=1)
    enter_category(card, DONE, t0 + timedelta(days=4))
    enter_category(card, CANCELED, t0 + timedelta(days=5))
    assert card.completed_at == t0 + timedelta(days=4)
    enter_category(card, DOING, t0 + timedelta(days=6))
    assert card.completed_at is None
    assert card.started_at == t0 + timedelta(days=1)
