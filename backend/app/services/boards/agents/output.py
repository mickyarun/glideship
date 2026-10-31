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

"""Saving what a card run produced: the draft the tool wrote, else the reply as one.

The run row is locked first and must still be ``running``; a run canceled
meanwhile (moved boards, AI switched off, gone stale) saves nothing and its
job ends canceled. An empty reply with no draft fails the run, as does a
reply over ``CARD_DOC_MAX_CHARS``.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_agent import BoardAgentRunStatus
from app.models.board_enums import BoardCardDocKind
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card_doc import BoardCardDocRepository
from app.services.agents.subject import AgentRunCanceledError
from app.services.boards.agents.drafts import write_draft
from app.services.boards.agents.refs import RunRefs
from app.services.boards.agents.runs import stop_reason
from app.services.boards.constants import CARD_DOC_MAX_CHARS

NO_OUTPUT = "The agent finished without writing a draft."
TOO_LONG = f"The agent's reply was over {CARD_DOC_MAX_CHARS} characters, so no draft was saved."


class EmptyOutputError(Exception):
    """The agent wrote no draft and replied with nothing to save (or too much)."""


async def save_output(
    db: AsyncSession, refs: RunRefs, kind: BoardCardDocKind, output: str
) -> dict[str, Any]:
    """The run's result summary: the draft the tool wrote, else the reply saved as one.

    Raises:
        AgentRunCanceledError: The run stopped meanwhile; nothing is saved.
        EmptyOutputError: No draft and an empty (or oversized) reply.
    """
    run = refs.run
    await BoardCardAgentRunRepository(db, org_id=run.org_id).lock(run)
    if run.status is not BoardAgentRunStatus.RUNNING:
        raise AgentRunCanceledError(stop_reason(run))
    drafted = await BoardCardDocRepository(db, org_id=run.org_id).written_by_run(run.id)
    if drafted is not None:
        return {"kind": drafted.kind.value, "version": drafted.version, "via": "tool"}
    if not output.strip():
        raise EmptyOutputError(NO_OUTPUT)
    if len(output) > CARD_DOC_MAX_CHARS:
        raise EmptyOutputError(TOO_LONG)
    doc = await write_draft(db, refs.board, refs.card, kind, output, run_id=run.id)
    return {"kind": doc.kind.value, "version": doc.version, "via": "reply"}
