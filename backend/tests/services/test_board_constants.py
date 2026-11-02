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

"""Board keys, handover landings and the action-to-role table."""

from __future__ import annotations

import pytest

from app.models.board import Board
from app.models.board_enums import BoardMemberRole
from app.models.bud import BUDStatus
from app.services.boards.constants import (
    BOARD_ACTION_MIN_ROLE,
    BOARD_KEY_MAX_LENGTH,
    BOARD_KEY_MIN_LENGTH,
    BOARD_KEY_PATTERN,
    HANDOVER_LANDING_STATUSES,
    RESERVED_BOARD_KEYS,
    BoardAction,
    capabilities_for,
)


@pytest.mark.parametrize("key", ["SEO", "OP", "ABCDEFGHIJ"])
def test_board_keys_are_two_to_ten_uppercase_letters(key: str) -> None:
    assert BOARD_KEY_PATTERN.fullmatch(key)


@pytest.mark.parametrize("key", ["S", "seo", "SE1", "SE-O", "ABCDEFGHIJK", ""])
def test_malformed_board_keys_do_not_match(key: str) -> None:
    assert BOARD_KEY_PATTERN.fullmatch(key) is None


def test_bud_and_bug_prefixes_are_reserved() -> None:
    assert {"BUD", "BUG"} <= RESERVED_BOARD_KEYS


def test_handover_lands_before_development() -> None:
    assert HANDOVER_LANDING_STATUSES == (BUDStatus.BUD, BUDStatus.DESIGN, BUDStatus.TECH_ARCH)


def test_every_action_has_a_minimum_role() -> None:
    assert set(BOARD_ACTION_MIN_ROLE) == set(BoardAction)


def test_roles_rank_viewer_editor_admin() -> None:
    viewer, editor, admin = BoardMemberRole.VIEWER, BoardMemberRole.EDITOR, BoardMemberRole.ADMIN
    assert admin.at_least(editor) and editor.at_least(viewer) and viewer.at_least(viewer)
    assert not viewer.at_least(editor) and not editor.at_least(admin)


def test_capabilities_grow_with_the_role() -> None:
    viewer = set(capabilities_for(BoardMemberRole.VIEWER))
    editor = set(capabilities_for(BoardMemberRole.EDITOR))
    admin = set(capabilities_for(BoardMemberRole.ADMIN))
    assert viewer == {BoardAction.VIEW, BoardAction.COMMENT}
    assert viewer < editor < admin == set(BoardAction)
    assert BoardAction.MOVE_CARD in editor and BoardAction.MANAGE_STAGES not in editor


def test_key_length_bounds_match_the_pattern_and_column() -> None:
    assert (BOARD_KEY_MIN_LENGTH, BOARD_KEY_MAX_LENGTH) == (2, 10)
    assert Board.__table__.c.key.type.length == BOARD_KEY_MAX_LENGTH
