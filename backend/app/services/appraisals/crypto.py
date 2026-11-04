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

"""HR-key encryption for every free-text appraisal field.

Each blob is bound to its org, its owner (the employee profile, or the
cycle or goal for rows that have no profile), its table, its row and its
field, so ciphertext copied anywhere else fails to decrypt. Profiles and
goals keep their ids across account merges, so merges never break a blob.

``SEALED`` lists every encrypted column. Key rotation walks it, so a new
encrypted column only needs adding here.
"""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core import hr_crypto
from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_evidence_link import AppraisalEvidenceLink
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.base import BaseModel


def _profile(row: Any) -> str:
    return f"profile:{row.profile_id}"


def _goal(row: Any) -> str:
    return f"goal:{row.goal_id}"


@dataclass(frozen=True)
class SealedTable:
    """One table's encrypted columns and whose data they are."""

    model: type[BaseModel]
    fields: tuple[str, ...]
    owner: Callable[[Any], str]


SEALED: tuple[SealedTable, ...] = (
    SealedTable(AppraisalCycle, ("intro_note",), lambda row: "cycle"),
    SealedTable(AppraisalCheckIn, ("ai_summary", "employee_note"), _profile),
    SealedTable(
        Appraisal,
        (
            "ai_period_summary",
            "self_reason",
            "manager_reason",
            "concern_note",
            "send_back_note",
            "growth_strength",
            "growth_focus",
            "reply",
        ),
        _profile,
    ),
    SealedTable(
        AppraisalGoal,
        ("title", "measure", "original", "dismiss_reason", "self_reason", "manager_reason"),
        _profile,
    ),
    SealedTable(AppraisalGoalRevision, ("before", "after", "reason"), _goal),
    SealedTable(AppraisalManagerFeedback, ("keep_note", "try_note", "goal_notes"), _profile),
    SealedTable(AppraisalEvidenceLink, ("url", "title"), _profile),
    SealedTable(AppraisalGoalValue, ("value", "source_note", "source_url"), _goal),
)

_BY_MODEL: dict[type[BaseModel], SealedTable] = {t.model: t for t in SEALED}


def _table(row: BaseModel, field: str) -> SealedTable:
    table = _BY_MODEL.get(type(row))
    if table is None or field not in table.fields:
        raise ValueError(f"{type(row).__name__}.{field} is not an encrypted appraisal field.")
    return table


def aad(row: BaseModel, field: str) -> str:
    """Associated data for one field of one row."""
    table = _table(row, field)
    org_id = getattr(row, "org_id")  # noqa: B009 - every appraisal table has it
    return f"{org_id}|{table.owner(row)}|{table.model.__tablename__}|{row.id}|{field}"


def seal(row: BaseModel, field: str, text: str | None) -> None:
    """Encrypt ``text`` into ``row.field``; empty text clears it.

    Gives the row its id first if it has none yet, because the id is part
    of the binding and the model's default only fills it in at flush.
    """
    _table(row, field)
    if row.id is None:
        row.id = uuid.uuid4()
    blob = hr_crypto.encrypt(text.encode(), aad(row, field)) if text else None
    setattr(row, field, blob)


def unseal(row: BaseModel, field: str) -> str | None:
    """The decrypted text of ``row.field``, or None when it is empty."""
    blob: bytes | None = getattr(row, field)
    return hr_crypto.decrypt(blob, aad(row, field)).decode() if blob else None


def seal_json(row: BaseModel, field: str, value: Any) -> None:
    """Encrypt a JSON value (lines under headings, a goal before an edit)."""
    seal(row, field, json.dumps(value, separators=(",", ":")) if value is not None else None)


def unseal_json(row: BaseModel, field: str) -> Any:
    """The decrypted JSON value of ``row.field``, or None when it is empty."""
    text = unseal(row, field)
    return json.loads(text) if text is not None else None
