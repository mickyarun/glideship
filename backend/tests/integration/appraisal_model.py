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

"""A stand-in for the AI model in appraisal sweeper tests."""

import uuid
from typing import Any

import pytest
from sqlalchemy import update

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftStatus
from app.services.appraisals import draft_sweeper
from app.services.claude_runner import ClaudeRunResult
from tests.integration.leave_support import Factory


class Model:
    """Stands in for the model; ``calls`` counts every run."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.reply: Any = lambda _p: ClaudeRunResult(success=False, output="", error="x")

    async def __call__(self, _org: uuid.UUID, prompt: str) -> ClaudeRunResult:
        self.calls.append(prompt)
        result = self.reply(prompt)
        return await result if hasattr(result, "__await__") else result


@pytest.fixture
async def model(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Model:
    """A stand-in model, with other tests' waiting drafts cleared out of its way."""
    stand_in = Model()
    monkeypatch.setattr(draft_sweeper, "AsyncSessionLocal", pg_session_factory)
    monkeypatch.setattr(draft_sweeper, "run_draft", stand_in)
    async with pg_session_factory() as db:
        for table, column in (
            (AppraisalCheckIn, AppraisalCheckIn.draft_status),
            (Appraisal, Appraisal.period_summary_status),
            (Appraisal, Appraisal.suggest_status),
        ):
            await db.execute(
                update(table).where(column == DraftStatus.PENDING).values({column.key: "none"})
            )
        await db.commit()
    return stand_in
