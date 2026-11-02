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

"""Which stage a card lands in when it moves to another board."""

import uuid

import pytest

from app.models.board import BoardStage
from app.models.board_enums import BoardStageCategory
from app.services.boards.card_carry import pick_stage
from app.services.boards.errors import BoardItemNotFoundError

TODO, DOING = BoardStageCategory.TODO, BoardStageCategory.IN_PROGRESS
DONE, CANCELED = BoardStageCategory.DONE, BoardStageCategory.CANCELED


def _stage(name: str, category: BoardStageCategory, *, default: bool = False) -> BoardStage:
    return BoardStage(id=uuid.uuid4(), name=name, category=category, is_default=default)


TARGET = [
    _stage("Inbox", TODO, default=True),
    _stage("Doing", DOING),
    _stage("Review", DOING),
    _stage("Shipped", DONE),
]


def test_an_explicit_stage_wins_and_must_be_on_the_target() -> None:
    assert pick_stage(TARGET, _stage("Doing", DOING), TARGET[3].id) is TARGET[3]
    with pytest.raises(BoardItemNotFoundError):
        pick_stage(TARGET, _stage("Doing", DOING), uuid.uuid4())


def test_same_name_then_same_category_then_the_default() -> None:
    assert pick_stage(TARGET, _stage("review", TODO), None) is TARGET[2]
    assert pick_stage(TARGET, _stage("Waiting", DOING), None) is TARGET[1]
    assert pick_stage(TARGET, _stage("Dropped", CANCELED), None) is TARGET[0]
