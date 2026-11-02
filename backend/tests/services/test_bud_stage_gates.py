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

"""Which sections each BUD stage needs written before a BUD enters it."""

import pytest
from fastapi import HTTPException

from app.models.bud import BUDStatus
from app.services.bud_stage_gates import (
    StageContent,
    assert_stage_content,
    has_text,
    missing_content,
)

PRD = "## Problem\nUsers can't export."
SPEC = "## Approach\nAdd an export job."


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (BUDStatus.BUD, []),
        (BUDStatus.DESIGN, [StageContent.PRD]),
        (BUDStatus.TECH_ARCH, [StageContent.PRD]),
        (BUDStatus.DEVELOPMENT, [StageContent.PRD, StageContent.TECH_SPEC]),
        (BUDStatus.PROD, [StageContent.PRD, StageContent.TECH_SPEC]),
        (BUDStatus.CLOSED, []),
        (BUDStatus.DISCARDED, []),
    ],
)
def test_an_empty_bud_needs_what_each_stage_builds_on(
    target: BUDStatus, expected: list[StageContent]
) -> None:
    assert missing_content(target, requirements_md=None, tech_spec_md=None) == expected


def test_a_written_prd_opens_design_but_not_development() -> None:
    assert missing_content(BUDStatus.DESIGN, requirements_md=PRD, tech_spec_md=None) == []
    assert missing_content(BUDStatus.DEVELOPMENT, requirements_md=PRD, tech_spec_md=None) == [
        StageContent.TECH_SPEC
    ]
    assert missing_content(BUDStatus.TESTING, requirements_md=PRD, tech_spec_md=SPEC) == []


def test_whitespace_is_not_written() -> None:
    assert not has_text("  \n\t")
    assert not has_text(None)
    assert has_text(PRD)


def test_the_refusal_names_what_is_missing() -> None:
    with pytest.raises(HTTPException) as caught:
        assert_stage_content(BUDStatus.DEVELOPMENT, requirements_md="", tech_spec_md=None)
    assert caught.value.status_code == 409
    assert caught.value.detail == {
        "code": "bud_stage_content_missing",
        "target_status": "development",
        "missing": ["prd", "tech_spec"],
        "message": "A BUD needs a PRD and a tech spec before it can move to development.",
    }
