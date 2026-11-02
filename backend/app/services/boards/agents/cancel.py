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

"""Canceling a card's agent run from its AI panel.

An editor cancels a pending or running run: it is settled ``canceled``
(code ``CANCELED``) with an ``ai_run`` event naming who did it, the board
hears ``agent_run_updated``, and after the commit its job is canceled the way
a move between boards cancels one (:func:`.runs.stop_job_after_commit`): a
queued job never starts and ends ``cancelled``; a running one goes through
the executor's cancel path, finds the run settled and saves nothing. Locks:
the card, then the run.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card import BoardCardRepository
from app.schemas.boards.agent import AgentRunRead
from app.services.boards.access import CardAccess
from app.services.boards.agents.apply import settle_canceled
from app.services.boards.agents.errors import AgentRunFinishedError
from app.services.boards.agents.loading import run_row
from app.services.boards.agents.runs import run_read, shows_run_errors, stop_job_after_commit
from app.services.boards.errors import BoardItemNotFoundError

RUN_NOT_FOUND = "Agent run not found."
CANCELED_BY_PERSON = "Someone on the board canceled this run."


async def cancel_run(db: AsyncSession, target: CardAccess, run_id: uuid.UUID) -> AgentRunRead:
    """Cancel the card's run ``run_id`` and commit; the run as it is now.

    Raises:
        BoardItemNotFoundError: No such run on this card (404).
        AgentRunFinishedError: The run already ended (409).
    """
    access, card = target.access, target.card
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    run = await BoardCardAgentRunRepository(db, org_id=access.org_id).get_by_id(run_id)
    row = None if run is None or run.card_id != card.id else await run_row(db, run)
    if run is None or row is None:
        raise BoardItemNotFoundError(RUN_NOT_FOUND)
    if not await settle_canceled(db, row, CANCELED_BY_PERSON, actor_id=access.user_id):
        raise AgentRunFinishedError(run.status)
    stop_job_after_commit(db, run, CANCELED_BY_PERSON)
    await db.commit()
    return run_read(run, show_error=shows_run_errors(target))
