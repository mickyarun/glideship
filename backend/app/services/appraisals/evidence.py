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

"""What can be cited as evidence in a review: the period's facts and links.

Evidence is picked from what the period already holds: each check-in's
facts, the period's own facts and the person's links. Facts are copied
in, as their refs hold only what their source keeps in plain text;
links are kept by id only, because their words are encrypted.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.services.appraisals.errors import AppraisalInvalidError

LINK = "link:"
Pool = dict[str, dict[str, Any]]


async def evidence_pool(
    db: AsyncSession, appraisal: Appraisal, check_ins: list[AppraisalCheckIn] | None = None
) -> Pool:
    """Everything in the period that can be cited, by id."""
    repo = AppraisalCheckInRepository(db, org_id=appraisal.org_id)
    months = check_ins
    if months is None:
        months = await repo.for_person_in_cycle(appraisal.profile_id, appraisal.cycle_id)
    pool: Pool = {}
    links = await repo.links_for([c.id for c in months])
    for check_in in months:
        pool.update({str(f["id"]): f for f in check_in.fact_refs or []})
        for link in links[check_in.id]:
            key = f"{LINK}{link.id}"
            pool[key] = {"source": "link", "id": key}
    pool.update({str(f["id"]): f for f in appraisal.period_facts or []})
    return pool


def pick(pool: Pool, ids: list[str]) -> list[dict[str, Any]]:
    """The refs for these ids, in order and once each; unknown ids are refused."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in ids:
        if item not in pool:
            raise AppraisalInvalidError("Evidence must come from this period's check-ins.")
        if item not in seen:
            seen.add(item)
            out.append(pool[item])
    return out


def ids_of(refs: list[dict[str, Any]] | None) -> list[str]:
    """The ids of saved evidence."""
    return [str(ref["id"]) for ref in refs or []]
