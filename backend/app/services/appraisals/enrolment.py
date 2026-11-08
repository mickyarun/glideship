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

"""Who is in a cycle: enrolment when it opens, late joiners, exits and manager moves.

Each enrolled person gets an appraisal row holding a snapshot of their
primary manager (who scores), their role template and the drafting mode.
Nobody without a primary manager is enrolled: the report lists them for
HR, and the daily tick picks them up once HR sets one, until the cut-off.
"""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus, DraftStatus
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.models.employee_audit_event import EmployeeAuditAction
from app.models.employee_profile import EmployeeProfile, EmployeeStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.employee_reporting_manager import (
    EmployeeReportingManagerRepository,
    ManagerLink,
)
from app.schemas.appraisal_cycle import EnrolmentReport
from app.services.appraisals import audit
from app.services.appraisals.cycles import draft_cycle
from app.services.appraisals.drafting_mode import drafting_mode
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.role_templates import ensure_seeded, match_template
from app.services.appraisals.settings import load_appraisal_settings

# Moving to either status withdraws the person's appraisals in progress.
LEAVING = frozenset({EmployeeStatus.ON_NOTICE, EmployeeStatus.EXITED})


def primary_link(links: Sequence[ManagerLink]) -> ManagerLink | None:
    """The person's active primary manager link, if any."""
    return next((m for m in links if m.is_primary and m.is_active), None)


def in_scope(
    cycle: AppraisalCycle, profile: EmployeeProfile, template: AppraisalRoleTemplate | None
) -> bool:
    """Whether the cycle's offices, departments and templates cover the person."""
    scope = cycle.scope or {}
    offices = set(scope.get("offices") or [])
    departments = {d.lower() for d in scope.get("departments") or []}
    templates = set(scope.get("templates") or [])
    return (
        (not offices or str(profile.office_id) in offices)
        and (not departments or (profile.department or "").lower() in departments)
        and (not templates or (template is not None and str(template.id) in templates))
    )


async def enrol(
    db: AsyncSession,
    cycle: AppraisalCycle,
    templates: Sequence[AppraisalRoleTemplate],
    profiles: Sequence[EmployeeProfile],
) -> EnrolmentReport:
    """Create an appraisal for each in-scope person not yet in the cycle."""
    settings = await load_appraisal_settings(db, cycle.org_id)
    repo = AppraisalRepository(db, org_id=cycle.org_id)
    links = await EmployeeReportingManagerRepository(db, org_id=cycle.org_id).list_for_profiles(
        [p.id for p in profiles]
    )
    enrolled_ids = {a.profile_id for a in await repo.for_cycle(cycle.id)}
    report = EnrolmentReport(enrolled=0, already_enrolled=0, no_primary_manager=[], no_template=[])
    for profile in profiles:
        template = match_template(
            templates, profile.department, profile.designation, cycle.template_overrides
        )
        if not in_scope(cycle, profile, template):
            continue
        if profile.id in enrolled_ids:
            report.already_enrolled += 1
            continue
        primary = primary_link(links.get(profile.id, []))
        if primary is None:
            report.no_primary_manager.append(profile.user_id)
            continue
        if template is None:
            report.no_template.append(profile.user_id)
        db.add(
            Appraisal(
                org_id=cycle.org_id,
                cycle_id=cycle.id,
                profile_id=profile.id,
                manager_user_id=primary.user_id,
                role_template_id=template.id if template else None,
                drafting_mode=drafting_mode(
                    org_ai=settings.ai_enabled,
                    cycle_ai=cycle.ai_drafting,
                    template_ai=bool(template and template.ai_drafting),
                ),
            )
        )
        report.enrolled += 1
    await db.flush()
    return report


async def activate(
    db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID, actor_id: uuid.UUID
) -> EnrolmentReport:
    """Open a draft cycle and enrol everyone in its scope."""
    cycles = AppraisalCycleRepository(db, org_id=org_id)
    # Under the lock, so two activations can't both pass the overlap check.
    await cycles.lock_org()
    cycle = await draft_cycle(db, org_id, cycle_id)
    clash = await cycles.overlapping_running(cycle.period_start, cycle.period_end, cycle.id)
    if clash is not None:
        raise AppraisalConflictError(f"{clash.name} already covers part of this period.")
    templates = await ensure_seeded(db, org_id, actor_id)
    profiles = await AppraisalRepository(db, org_id=org_id).enrollable_profiles(
        cycle.enrolment_cutoff
    )
    report = await enrol(db, cycle, templates, profiles)
    cycle.status = CycleStatus.ACTIVE
    await db.flush()
    if cycle.suggest_goals_on_open:
        await AppraisalRepository(db, org_id=org_id).queue_suggestions(cycle.id)
    return report


async def enrol_late_joiners(db: AsyncSession, org_id: uuid.UUID, today: date) -> int:
    """Enrol anyone who became eligible after their cycle opened, until its cut-off."""
    total = 0
    templates: Sequence[AppraisalRoleTemplate] | None = None
    repo = AppraisalRepository(db, org_id=org_id)
    for cycle in await AppraisalCycleRepository(db, org_id=org_id).running_on(today):
        if today > cycle.enrolment_cutoff:
            continue
        templates = templates or await ensure_seeded(db, org_id, None)
        enrolled = [a.profile_id for a in await repo.for_cycle(cycle.id)]
        fresh = await repo.enrollable_profiles(cycle.enrolment_cutoff, exclude=enrolled)
        if fresh:
            total += (await enrol(db, cycle, templates, fresh)).enrolled
    return total


async def withdraw_on_exit(db: AsyncSession, org_id: uuid.UUID, profile_id: uuid.UUID) -> int:
    """Withdraw the person's appraisals still in progress when they go on notice or leave."""
    open_ones = await AppraisalRepository(db, org_id=org_id).open_for_profile(profile_id)
    for appraisal in open_ones:
        appraisal.status = AppraisalStatus.WITHDRAWN
        if appraisal.period_summary_status is DraftStatus.PENDING:
            appraisal.period_summary_status = DraftStatus.NONE
    # Nothing more about them goes to the AI provider.
    await AppraisalCheckInRepository(db, org_id=org_id).cancel_pending_drafts(profile_id)
    await db.flush()
    return len(open_ones)


async def follow_primary_manager(
    db: AsyncSession, org_id: uuid.UUID, profile: EmployeeProfile, actor_id: uuid.UUID
) -> int:
    """Move open appraisals and feedback to the person's current primary manager.

    With no primary manager left, the snapshot stays; the access rules
    already stop a manager who left the reporting line from scoring. Each
    moved appraisal is audited, since the new scorer reads everything.
    """
    profile_id = profile.id
    links = await EmployeeReportingManagerRepository(db, org_id=org_id).list_for_profiles(
        [profile_id]
    )
    primary = primary_link(links.get(profile_id, []))
    if primary is None:
        return 0
    moved = await AppraisalRepository(db, org_id=org_id).move_scorer(profile_id, primary.user_id)
    for appraisal_id in moved:
        audit.record(
            db,
            org_id=org_id,
            actor_id=actor_id,
            subject_user_id=profile.user_id,
            profile_id=profile_id,
            action=EmployeeAuditAction.APPRAISAL_CHANGED,
            target=appraisal_id,
        )
    feedback = await AppraisalFeedbackRepository(db, org_id=org_id).move_open(
        profile_id, primary.user_id
    )
    return len(moved) + feedback
