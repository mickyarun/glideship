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

"""What a BUD must have written before it can enter a stage.

A BUD's PRD is written at the ``bud`` stage and its tech spec at
``tech_arch`` (see :mod:`app.services.bud_edit_policy`), so a BUD can't
reach design or later without a PRD, or development or later without a
tech spec. Closing and discarding stay open at any stage: they end the
BUD rather than deliver it.

Only a person's stage change (the status PATCH) is gated. The flows that
move a BUD on their own (PR merges, release detection, handover landing)
run after the content they depend on exists.

Frontend mirror: ``BUD_STAGE_NEEDS`` in ``frontend/src/utils/budStageGates.ts``.
"""

from enum import StrEnum
from typing import NoReturn

from fastapi import HTTPException, status

from app.models.bud import BUDStatus


class StageContent(StrEnum):
    """A section a stage needs written before a BUD enters it."""

    PRD = "prd"
    TECH_SPEC = "tech_spec"


_DELIVERY_FROM_DESIGN: frozenset[BUDStatus] = frozenset(
    {
        BUDStatus.DESIGN,
        BUDStatus.TECH_ARCH,
        BUDStatus.DEVELOPMENT,
        BUDStatus.CODE_REVIEW,
        BUDStatus.TESTING,
        BUDStatus.UAT,
        BUDStatus.PROD,
    }
)
_DELIVERY_FROM_DEVELOPMENT: frozenset[BUDStatus] = _DELIVERY_FROM_DESIGN - {
    BUDStatus.DESIGN,
    BUDStatus.TECH_ARCH,
}

_CONTENT_NAMES: dict[StageContent, str] = {
    StageContent.PRD: "a PRD",
    StageContent.TECH_SPEC: "a tech spec",
}


def has_text(markdown: str | None) -> bool:
    """Whether a section has anything written in it."""
    return bool(markdown and markdown.strip())


def missing_content(
    target: BUDStatus, *, requirements_md: str | None, tech_spec_md: str | None
) -> list[StageContent]:
    """The sections ``target`` needs that aren't written yet, PRD first."""
    missing: list[StageContent] = []
    if target in _DELIVERY_FROM_DESIGN and not has_text(requirements_md):
        missing.append(StageContent.PRD)
    if target in _DELIVERY_FROM_DEVELOPMENT and not has_text(tech_spec_md):
        missing.append(StageContent.TECH_SPEC)
    return missing


def _raise_content_missing(target: BUDStatus, missing: list[StageContent]) -> NoReturn:
    needs = " and ".join(_CONTENT_NAMES[m] for m in missing)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "bud_stage_content_missing",
            "target_status": target.value,
            "missing": [m.value for m in missing],
            "message": f"A BUD needs {needs} before it can move to {target.value}.",
        },
    )


def assert_stage_content(
    target: BUDStatus, *, requirements_md: str | None, tech_spec_md: str | None
) -> None:
    """HTTP wrapper: raise 409 ``bud_stage_content_missing`` when a section is missing."""
    missing = missing_content(target, requirements_md=requirements_md, tech_spec_md=tech_spec_md)
    if missing:
        _raise_content_missing(target, missing)
