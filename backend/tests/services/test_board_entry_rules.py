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

"""The stage entry rules on their own: the field registry, the causes and the checklist."""

import uuid

import pytest

from app.models.board import BoardStage
from app.models.board_enums import BoardStageCategory, StageRequiredField
from app.services.boards.card_facts import REQUIRED_FIELD_TESTS, NewCardFacts, missing_fields
from app.services.boards.constants import STAGE_REQUIRED_FIELD_LABELS
from app.services.boards.errors import BoardRuleError
from app.services.boards.move_rules import (
    ENTRY_RULES,
    ChecklistOpenError,
    EntryCause,
    StageRequirementsMissingError,
    enter_stage,
)
from app.services.boards.stage_rules import check_default_stage_entry

TODO, DOING = BoardStageCategory.TODO, BoardStageCategory.IN_PROGRESS
DONE, CANCELED = BoardStageCategory.DONE, BoardStageCategory.CANCELED
OPEN_ITEM = NewCardFacts(checklist_done=0, checklist_total=1)


def _stage(
    category: BoardStageCategory,
    *fields: StageRequiredField,
    is_default: bool = False,
) -> BoardStage:
    return BoardStage(
        id=uuid.uuid4(),
        name=f"{category.value} stage",
        category=category,
        required_fields=list(fields),
        is_default=is_default,
    )


class _Loader:
    def __init__(self, facts: NewCardFacts) -> None:
        self.facts, self.calls = facts, 0

    async def __call__(self) -> NewCardFacts:
        self.calls += 1
        return self.facts


def test_every_required_field_has_one_test_and_one_label() -> None:
    assert set(REQUIRED_FIELD_TESTS) == set(StageRequiredField)
    assert set(STAGE_REQUIRED_FIELD_LABELS) == set(StageRequiredField)


def test_every_cause_says_which_rules_it_applies() -> None:
    assert set(ENTRY_RULES) == set(EntryCause)
    chosen = {cause for cause, rules in ENTRY_RULES.items() if rules.required_fields}
    assert chosen == {EntryCause.MOVE, EntryCause.MOVE_BOARD, EntryCause.CREATE}
    assert all(r.required_fields == r.open_checklist for r in ENTRY_RULES.values())


def test_missing_fields_come_back_in_declaration_order() -> None:
    required = [StageRequiredField.PRD, StageRequiredField.ASSIGNEE]
    assert missing_fields(NewCardFacts(), required) == [
        StageRequiredField.ASSIGNEE,
        StageRequiredField.PRD,
    ]
    assert missing_fields(NewCardFacts(assignee_ids=[uuid.uuid4()], has_prd=True), required) == []


@pytest.mark.parametrize("cause", [EntryCause.RESTORE, EntryCause.STAGE_DELETE, EntryCause.IMPORT])
async def test_placing_causes_skip_both_rules_without_reading_the_card(cause: EntryCause) -> None:
    loader = _Loader(OPEN_ITEM)
    stage = _stage(DONE, *StageRequiredField)
    assert await enter_stage(stage, cause=cause, from_stage=_stage(TODO), facts=loader) is None
    assert loader.calls == 0


@pytest.mark.parametrize("cause", [EntryCause.MOVE, EntryCause.MOVE_BOARD, EntryCause.CREATE])
async def test_choosing_causes_apply_the_required_fields(cause: EntryCause) -> None:
    stage = _stage(DOING, StageRequiredField.DUE_DATE)
    with pytest.raises(StageRequirementsMissingError) as raised:
        await enter_stage(stage, cause=cause, facts=_Loader(NewCardFacts()))
    assert raised.value.missing == [StageRequiredField.DUE_DATE]


async def test_a_reorder_in_the_same_stage_is_not_an_entry() -> None:
    stage = _stage(DONE, StageRequiredField.LABEL)
    loader = _Loader(OPEN_ITEM)
    assert await enter_stage(stage, cause=EntryCause.MOVE, from_stage=stage, facts=loader) is None
    assert loader.calls == 0


async def test_a_choosing_cause_needs_the_cards_facts() -> None:
    with pytest.raises(TypeError):
        await enter_stage(_stage(DOING), cause=EntryCause.MOVE, from_stage=_stage(TODO))


@pytest.mark.parametrize(
    ("source", "target", "refused"),
    [
        (TODO, DONE, True),
        (DOING, DONE, True),
        (DONE, DONE, False),
        (CANCELED, DONE, False),
        (TODO, CANCELED, False),
    ],
)
async def test_the_checklist_rule_applies_only_when_a_card_completes_in_done(
    source: BoardStageCategory, target: BoardStageCategory, refused: bool
) -> None:
    move = enter_stage(
        _stage(target), cause=EntryCause.MOVE, from_stage=_stage(source), facts=_Loader(OPEN_ITEM)
    )
    if refused:
        with pytest.raises(ChecklistOpenError):
            await move
    else:
        assert await move == OPEN_ITEM


async def test_confirming_lets_open_items_through_and_the_loaded_facts_come_back() -> None:
    got = await enter_stage(
        _stage(DONE),
        cause=EntryCause.MOVE,
        from_stage=_stage(TODO),
        facts=_Loader(OPEN_ITEM),
        confirm_open_checklist=True,
    )
    assert got == OPEN_ITEM


def test_the_checklist_message_agrees_with_the_count() -> None:
    assert str(ChecklistOpenError(1, 3)) == "1 of 3 checklist items is still open."
    assert str(ChecklistOpenError(2, 3)) == "2 of 3 checklist items are still open."


def test_the_default_stage_cant_require_a_prd() -> None:
    check_default_stage_entry([_stage(TODO, StageRequiredField.ASSIGNEE, is_default=True)])
    check_default_stage_entry([_stage(DOING, StageRequiredField.PRD)])
    with pytest.raises(BoardRuleError, match="no PRD yet"):
        check_default_stage_entry([_stage(TODO, StageRequiredField.PRD, is_default=True)])
