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

"""Runs one agent job for any :class:`AgentSubject`.

The order is fixed here so BUD and card agents behave the same way: load,
build the prompt, mint the MCP grant, record the start, call the org's
provider through ``run_agent_for_org_id`` (so its provider and capability gate
apply), then save the output or record the failure. A cancel rolls the session
back, lets the subject record the reason and re-raises so the worker emits the
terminal event; any other error is recorded and fails the job.
"""

import asyncio

from app.database import AsyncSessionLocal
from app.schemas.jobs import JobState
from app.services.agents.subject import AgentRunRef, AgentSubject
from app.services.ai_runner import run_agent_for_org_id
from app.services.job_queue import get_job, update_job
from app.services.job_utils import make_progress_callback

DEFAULT_CANCEL_REASON = "Cancelled by user"


async def execute_agent_run(job_id: str, run: AgentRunRef, subject: AgentSubject) -> None:
    """Run ``subject``'s agent for job ``job_id`` and settle the job's state."""
    update_job(job_id, status_message="Loading task...", progress_pct=5)

    async with AsyncSessionLocal() as db:
        try:
            load_error = await subject.load(db)
            if load_error is not None:
                update_job(job_id, state=JobState.FAILED, error=load_error)
                return

            update_job(job_id, status_message="Building prompt...", progress_pct=10)
            prompt = await subject.build_prompt(db)
            subject.log_phase(
                "prompt_built",
                task_id=str(run.run_id),
                prompt_length=len(prompt.text),
                working_dir=prompt.working_dir,
            )

            update_job(job_id, status_message="Running agent...", progress_pct=20)
            launch = await subject.prepare(db, prompt, subject.mcp_grant())
            result = await run_agent_for_org_id(
                run.org_id,
                prompt=prompt.text,
                working_dir=launch.spawn_cwd,
                config=launch.config,
                progress_callback=make_progress_callback(job_id),
            )
            result = await subject.review(
                db, result, prompt, launch, make_progress_callback(job_id)
            )
            subject.log_phase(
                "claude_completed",
                task_id=str(run.run_id),
                success=result.success,
                output_length=len(result.output or ""),
                cost_usd=result.cost_usd,
                turns_used=result.turns_used,
            )

            if not result.success:
                error_msg = result.error or "Agent execution failed"
                await subject.record_failure(db, error_msg)
                update_job(
                    job_id,
                    state=JobState.FAILED,
                    error=error_msg,
                    error_code=result.error_code,
                )
                return

            update_job(job_id, status_message="Saving results...", progress_pct=90)
            summary = await subject.handle_output(db, result.output or "")
            await subject.record_success(db, summary)

        except asyncio.CancelledError:
            await db.rollback()
            # ``cancel_job`` stashes the reason on the job's status message
            # before it cancels the asyncio task.
            job = get_job(job_id)
            reason = (job.status_message if job else None) or DEFAULT_CANCEL_REASON
            await subject.record_cancel(reason)
            raise  # the worker's CancelledError branch emits the terminal event

        except Exception as exc:
            await db.rollback()
            await subject.record_crash(exc)
            update_job(job_id, state=JobState.FAILED, error=str(exc)[:200])
            return

    await subject.after_success()
    update_job(job_id, state=JobState.COMPLETED, status_message="Done", progress_pct=100)
    subject.announce()
