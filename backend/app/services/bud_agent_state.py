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

"""What a BUD stage agent task's run holds: its ids, the rows it loads, its CLI session.

The base of :class:`app.services.bud_agent_handler.BudAgentSubject`; the
loading lives in :mod:`app.services.bud_agent_loading` and the run-end
records in :mod:`app.services.bud_agent_records`.
"""

import uuid as uuid_mod
from typing import Any

from app.models.bud import BUDDocument
from app.models.bud_agent_task import BUDAgentTask
from app.schemas.bud_constants import BUD_AGENT_SECTIONS
from app.schemas.jobs import BUDAgentTaskPayload
from app.services.section_session import mint_session_id
from app.services.skill_loader import Skill


class BudAgentState:
    """A BUD agent task's ids and loaded rows."""

    def __init__(self, job_id: str, payload: BUDAgentTaskPayload) -> None:
        self.job_id = job_id
        self.payload = payload
        self.task_id = uuid_mod.UUID(payload.task_id)
        self.org_id = uuid_mod.UUID(payload.org_id)
        self.bud_id = uuid_mod.UUID(payload.bud_id)
        # Pre-set so the failure paths can always log / write activity rows
        # even before the real skill and task type are resolved.
        self.skill_slug = "bud_agent"
        self.task_type = "unknown"
        self.bud_number: int | None = None
        self.bud_title: str | None = None
        self.repo_id: uuid_mod.UUID | None = None
        self.repo_paths: list[str] = []
        self.session_section: str | None = None
        self.session_id: uuid_mod.UUID | None = None
        self._task: BUDAgentTask | None = None
        self._bud: BUDDocument | None = None
        self._skill: Skill | None = None

    @property
    def task(self) -> BUDAgentTask:
        """The loaded task row."""
        assert self._task is not None  # set by load()
        return self._task

    @property
    def bud(self) -> BUDDocument:
        """The loaded BUD."""
        assert self._bud is not None  # set by load()
        return self._bud

    @property
    def skill(self) -> Skill:
        """The loaded skill."""
        assert self._skill is not None  # set by load()
        return self._skill

    def log_phase(self, phase: str, **fields: Any) -> None:
        """Log one step of the run (the subject logs under its own event name)."""
        raise NotImplementedError

    def session_for_run(self) -> tuple[uuid_mod.UUID | None, bool]:
        """The CLI session id to use, and whether it resumes an earlier one.

        Agents owning a BUD section that chat resumes get a session id; a
        re-run with ``resume_session_id`` resumes that session instead of
        minting one, keeping the prompt cache warm.
        """
        self.session_section = BUD_AGENT_SECTIONS.get(self.task_type)
        if self.session_section is None:
            return None, False
        if self.task.resume_session_id is not None:
            return self.task.resume_session_id, True
        return mint_session_id(), False
