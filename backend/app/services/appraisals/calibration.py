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

"""HR's calibration view: each manager's bands, agreement and big gaps.

Bands and states only, never reasons. HR never changes a band; they send
a review back with a note, or share it.
"""

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_review import Calibration, CalibrationPerson, CalibrationTeam
from app.services.appraisals.calibration_math import Scored, figures
from app.services.appraisals.context import Caller
from app.services.appraisals.hr_scope import hidden_users


async def visible_appraisals(
    db: AsyncSession, caller: Caller, cycle: AppraisalCycle
) -> list[Appraisal]:
    """The cycle's appraisals HR may act on: not their own, not their manager's."""
    repo = AppraisalRepository(db, org_id=cycle.org_id)
    hidden = await hidden_users(db, caller)
    everyone = await repo.for_cycle(cycle.id)
    profiles = await repo.profiles_by_id([a.profile_id for a in everyone])
    return [
        a
        for a in everyone
        if (p := profiles.get(a.profile_id)) is not None and p.user_id not in hidden
    ]


async def calibration(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> Calibration:
    """Per-manager figures and one row per reviewed person."""
    appraisals = await visible_appraisals(db, caller, cycle)
    profiles = await AppraisalRepository(db, org_id=cycle.org_id).profiles_by_id(
        [a.profile_id for a in appraisals]
    )
    items = await AppraisalFeedbackRepository(db, org_id=cycle.org_id).for_cycles([cycle.id])
    feedback: dict[uuid.UUID, list[bool]] = defaultdict(list)
    for item in items:
        feedback[item.profile_id].append(item.status is FeedbackStatus.DONE)
    people_ids = {p.user_id for p in profiles.values()} | {a.manager_user_id for a in appraisals}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(people_ids))}
    rows: list[CalibrationPerson] = []
    teams: dict[uuid.UUID, list[Scored]] = defaultdict(list)
    for a in appraisals:
        final = a.final_band if a.manager_submitted_at else None
        if final is not None:
            teams[a.manager_user_id].append(Scored(a.self_band, final))
        done = feedback[a.profile_id]
        rows.append(
            CalibrationPerson(
                appraisal_id=a.id,
                name=names.get(profiles[a.profile_id].user_id, ""),
                manager_name=names.get(a.manager_user_id, ""),
                status=a.status,
                self_band=a.self_band if a.self_submitted_at else None,
                final_band=final,
                gap=final is not None
                and a.self_submitted_at is not None
                and a.self_band is not None
                and abs(a.self_band - final) >= 2,
                feedback=len(done),
                feedback_done=sum(done),
            )
        )
    team_rows = []
    for manager, scored in teams.items():
        figs = figures(scored)
        team_rows.append(
            CalibrationTeam(
                manager_name=names.get(manager, ""),
                people=len(scored),
                bands=figs.bands,
                agreement=figs.agreement,
                gaps=figs.gaps,
                flag=figs.flag,
            )
        )
    return Calibration(
        teams=sorted(team_rows, key=lambda t: t.manager_name.lower()),
        people=sorted(rows, key=lambda r: r.name.lower()),
    )
