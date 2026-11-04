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

"""Showing a saved fact to one viewer: in full, or as a "private record".

The person always sees their own work. Anyone else sees a card only if
they may open its board, engineering facts only with engineering access,
and HR facts only with employee-record access. A private fact still
counts as evidence; only its title and link are hidden.
"""

import uuid
from collections.abc import Collection, Sequence
from typing import Any

from app.core.permission_deps import PermissionSet
from app.core.permissions_people import WORKSPACE_ENGINEERING
from app.models.appraisal_enums import FactSource
from app.services.employees.access import MANAGE as EMPLOYEES_MANAGE

ENGINEERING_SOURCES = frozenset(
    {
        FactSource.BUDS.value,
        FactSource.PULL_REQUESTS.value,
        FactSource.CODE_REVIEWS.value,
        FactSource.BUGS.value,
        FactSource.QA_EVIDENCE.value,
    }
)
HR_RECORDS_PERMISSION = EMPLOYEES_MANAGE
PRIVATE_LABEL = {"board_cards": "Board", "hr_records": "HR"}


def board_ids(facts: Sequence[dict[str, Any]]) -> set[uuid.UUID]:
    """The boards a fact list's cards are on."""
    return {uuid.UUID(f["board_id"]) for f in facts if f.get("board_id")}


def _visible(fact: dict[str, Any], perms: PermissionSet, boards: Collection[uuid.UUID]) -> bool:
    source = fact.get("source")
    if source == FactSource.BOARD_CARDS.value:
        return bool(fact.get("board_id")) and uuid.UUID(fact["board_id"]) in boards
    if source in ENGINEERING_SOURCES:
        return perms.has(WORKSPACE_ENGINEERING)
    if source == FactSource.HR_RECORDS.value:
        return perms.has(HR_RECORDS_PERMISSION)
    return False


def for_viewer(
    facts: Sequence[dict[str, Any]],
    *,
    is_self: bool,
    perms: PermissionSet,
    boards: Collection[uuid.UUID],
) -> list[dict[str, Any]]:
    """The fact list as this viewer may see it (pure)."""
    shown = []
    for fact in facts:
        if is_self or _visible(fact, perms, boards):
            shown.append({**fact, "private": False})
        else:
            label = PRIVATE_LABEL.get(str(fact.get("source")), "Engineering")
            shown.append(
                {
                    "source": fact.get("source"),
                    "id": fact.get("id"),
                    "verb": fact.get("verb"),
                    "done_at": fact.get("done_at"),
                    "key": f"private record · {label}",
                    "title": None,
                    "url": None,
                    "board_id": None,
                    "private": True,
                }
            )
    return shown
