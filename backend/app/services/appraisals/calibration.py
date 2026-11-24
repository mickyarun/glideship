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
a review back with a note, or share it. A flagged result (a big gap, a
concern, or anyone on a team that rates high) is held out of sharing
everything that's ready until HR marks it fair.
"""

import uuid
from collections import Counter, defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, FeedbackStatus
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_calibration import Calibration, CalibrationPerson, CalibrationTeam
from app.services.appraisals.calibration_math import (
    Scored,
    figures,
    high_share,
    others,
    rates_high,
)
from app.services.appraisals.context import Caller
from app.services.appraisals.hr_scope import hidden_users
from app.services.appraisals.review_rules import submitted_band


async def visible_appraisals(
    db: AsyncSession, caller: Caller, cycle: AppraisalCycle
) -> tuple[list[Appraisal], dict[uuid.UUID, EmployeeProfile]]:
    """The cycle's appraisals HR may act on (not their own, not their manager's),
    and the profiles behind them."""
    repo = AppraisalRepository(db, org_id=cycle.org_id)
    hidden = await hidden_users(db, caller)
    everyone = await repo.for_cycle(cycle.id)
    profiles = {
        pid: p
        for pid, p in (await repo.profiles_by_id([a.profile_id for a in everyone])).items()
        if p.user_id not in hidden
    }
    return [a for a in everyone if a.profile_id in profiles], profiles


async def calibration(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> Calibration:
    """Per-manager figures and one row per reviewed person."""
    appraisals, profiles = await visible_appraisals(db, caller, cycle)
    items = await AppraisalFeedbackRepository(db, org_id=cycle.org_id).for_cycles([cycle.id])
    feedback: dict[uuid.UUID, list[bool]] = defaultdict(list)
    for item in items:
        feedback[item.profile_id].append(item.status is FeedbackStatus.DONE)
    people_ids = {p.user_id for p in profiles.values()} | {a.manager_user_id for a in appraisals}
    people_ids |= {a.looks_fair_by for a in appraisals if a.looks_fair_by}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(people_ids))}
    teams: dict[uuid.UUID, list[Scored]] = defaultdict(list)
    totals: Counter[uuid.UUID] = Counter()
    for a in appraisals:
        # Withdrawn people keep their row but leave the team's figures.
        if a.status is AppraisalStatus.WITHDRAWN:
            continue
        totals[a.manager_user_id] += 1
        if a.manager_submitted_at and a.final_band is not None:
            teams[a.manager_user_id].append(Scored(submitted_band(a), a.final_band))
    shares = {manager: high_share(teams[manager]) for manager in totals}
    high = rates_high(shares)
    rows = []
    for a in appraisals:
        final = a.final_band if a.manager_submitted_at else None
        own = submitted_band(a)
        gap = final is not None and own is not None and abs(own - final) >= 2
        concern = final is not None and bool(a.performance_concern)
        flagged = gap or concern or (final is not None and a.manager_user_id in high)
        done = feedback[a.profile_id]
        rows.append(
            CalibrationPerson(
                appraisal_id=a.id,
                name=names.get(profiles[a.profile_id].user_id, ""),
                manager_user_id=a.manager_user_id,
                manager_name=names.get(a.manager_user_id, ""),
                status=a.status,
                self_band=own,
                final_band=final,
                gap=gap,
                concern=concern,
                feedback=len(done),
                feedback_done=sum(done),
                held=flagged and a.looks_fair_at is None,
                looks_fair_at=a.looks_fair_at,
                looks_fair_by_name=names.get(a.looks_fair_by, "") if a.looks_fair_by else "",
            )
        )
    team_rows = []
    # Every manager with someone to score, so one still writing shows as 0 of N.
    for manager in totals:
        figs, rest = figures(teams[manager]), others(shares, manager)
        team_rows.append(
            CalibrationTeam(
                manager_user_id=manager,
                manager_name=names.get(manager, ""),
                people=len(teams[manager]),
                total=totals[manager],
                bands=figs.bands,
                agreement=figs.agreement,
                gaps=figs.gaps,
                flag=figs.flag,
                high=shares[manager].high,
                others_high=rest.high,
                others_people=rest.people,
                rates_high=manager in high,
            )
        )
    return Calibration(
        teams=sorted(team_rows, key=lambda t: t.manager_name.lower()),
        people=sorted(rows, key=lambda r: r.name.lower()),
    )
