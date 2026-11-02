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

"""Why the shared agent executor says a run was cancelled.

The reason ``cancel_job`` gave wins; a cancel while the queue shuts down is
the restart; never the job's last progress text.
"""

import pytest

from app.schemas.jobs import JobState, JobStatusRead
from app.services import job_queue
from app.services.agents import executor


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    jobs: dict[str, object] = {}
    monkeypatch.setattr(job_queue, "_job_store", jobs)
    monkeypatch.setattr(job_queue, "_cancel_reasons", {})
    monkeypatch.setattr(job_queue, "_shutting_down", False)
    status = JobStatusRead(
        job_id="j1",
        job_type="board_agent_run",
        state=JobState.RUNNING,
        status_message="Calling get_card_context...",
    )
    jobs["j1"] = job_queue._JobEntry(status, 0.0, None, {})
    return jobs


async def test_the_reason_cancel_job_gave_wins(store: dict[str, object]) -> None:
    job_queue.cancel_job("j1", reason="AI was switched off on this board.")
    assert executor._why_canceled("j1") == "AI was switched off on this board."


async def test_a_cancel_during_shutdown_is_the_restart_not_the_progress_text(
    store: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(job_queue, "_shutting_down", True)
    assert executor._why_canceled("j1") == executor.RESTART_REASON


async def test_otherwise_the_default_reason(store: dict[str, object]) -> None:
    assert executor._why_canceled("j1") == executor.DEFAULT_CANCEL_REASON
