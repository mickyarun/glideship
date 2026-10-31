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

"""The ``board_agent_run`` job: one stage agent's run on one card, through the shared executor."""

from typing import Any

from app.schemas.boards.agent import BoardAgentRunPayload
from app.services.agents.executor import execute_agent_run
from app.services.agents.subject import AgentRunRef
from app.services.boards.agents.subject import CardAgentSubject


async def handle_board_agent_run_job(job_id: str, raw_payload: dict[str, Any]) -> None:
    """Run the card agent the payload names."""
    payload = BoardAgentRunPayload.model_validate(raw_payload)
    run = AgentRunRef(org_id=payload.org_id, run_id=payload.run_id)
    await execute_agent_run(job_id, run, CardAgentSubject(job_id, payload))
