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

"""Board templates load from YAML and enforce the board's stage rules."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.config import settings
from app.models.board_enums import BoardStageCategory
from app.services.boards.board_template import load_templates, parse_template


def _template(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Test",
        "stages": [
            {"name": "To do", "category": "todo", "default": True},
            {"name": "Doing", "category": "in_progress"},
            {"name": "Done", "category": "done"},
        ],
    }
    return {**base, **overrides}


def test_every_shipped_template_loads() -> None:
    templates = load_templates()
    assert set(templates) == {"blank", "content-seo", "design", "ops", "product"}
    product = templates["product"]
    assert product.handover_stage == "Ready for dev"
    assert product.return_stage == "Ideas"
    assert [s.category for s in templates["ops"].stages].count(BoardStageCategory.TODO) == 2


def test_a_minimal_template_is_valid() -> None:
    assert parse_template(_template()).stages[0].default


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"stages": [{"name": "Done", "category": "done", "default": True}]},
            "at least one todo",
        ),
        (
            {"stages": [{"name": "To do", "category": "todo", "default": True}]},
            "at least one done",
        ),
        (
            {
                "stages": [
                    {"name": "To do", "category": "todo", "default": True},
                    {"name": "To do", "category": "done"},
                ]
            },
            "unique",
        ),
        (
            {
                "stages": [
                    {"name": "A", "category": "todo", "default": True},
                    {"name": "B", "category": "done", "default": True},
                ]
            },
            "exactly one stage",
        ),
        (
            {
                "stages": [
                    {"name": "A", "category": "todo"},
                    {"name": "B", "category": "done"},
                ]
            },
            "exactly one stage",
        ),
        ({"handover_stage": "Doing"}, "handover_stage must be a done stage"),
        ({"handover_stage": "Nowhere"}, "not one of the stages"),
        ({"handover_stage": "Done", "return_stage": "Done"}, "return_stage must be a todo"),
        ({"return_stage": "To do"}, "return_stage needs a handover_stage"),
        ({"colour": "blue"}, "Extra inputs"),
    ],
)
def test_invalid_templates_are_rejected(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_template(_template(**overrides))


def test_stage_count_is_capped_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.boards, "max_stages_per_board", 3)
    parse_template(_template())
    stages = [*_template()["stages"], {"name": "Extra", "category": "todo"}]
    with pytest.raises(ValidationError, match="at most 3 stages"):
        parse_template(_template(stages=stages))
