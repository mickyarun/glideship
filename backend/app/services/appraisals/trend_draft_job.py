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

"""The job that asks the AI for a role's trends and saves them as a draft.

HR asks from the role template screen; the answer is checked (sources
required) and saved as a draft for HR to edit and approve. A provider
without web search, or a run that fails, leaves the list as it was.
"""

import uuid
from typing import Any

import structlog

from app.database import AsyncSessionLocal
from app.schemas.jobs import JobState
from app.services.appraisals.draft_check import DraftUnreadableError
from app.services.appraisals.draft_runner import run_research
from app.services.appraisals.role_template_admin import get_template
from app.services.appraisals.role_trends import checked_trends, save_trends, trend_prompt
from app.services.job_queue import create_job, update_job

logger = structlog.get_logger(__name__)
JOB_APPRAISAL_TRENDS = "appraisal_trends"


def queue_trend_draft(org_id: uuid.UUID, template_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Start a draft; the job id to follow."""
    payload = {"org_id": str(org_id), "template_id": str(template_id)}
    return create_job(JOB_APPRAISAL_TRENDS, payload=payload, user_id=str(user_id)).job_id


async def handle_trend_draft_job(job_id: str, payload: dict[str, Any]) -> None:
    """Research, check and save the draft."""
    org_id, template_id = uuid.UUID(payload["org_id"]), uuid.UUID(payload["template_id"])
    update_job(job_id, state=JobState.RUNNING, status_message="Researching the role")
    async with AsyncSessionLocal() as db:
        prompt = trend_prompt(await get_template(db, org_id, template_id))
    result = await run_research(org_id, prompt)
    trends = []
    if result.success:
        try:
            trends = checked_trends(result.output)
        except DraftUnreadableError:
            trends = []
    if not trends:
        code = result.error_code.value if result.error_code else "no_sourced_trends"
        logger.warning("appraisal_trends_draft_failed", org_id=str(org_id), code=code)
        update_job(
            job_id,
            state=JobState.FAILED,
            error="No trends with a source came back. Write them by hand instead.",
            error_code=code,
        )
        return
    async with AsyncSessionLocal() as db:
        await save_trends(db, org_id, template_id, trends)
        await db.commit()
    update_job(job_id, state=JobState.COMPLETED, result={"trends": len(trends)})
