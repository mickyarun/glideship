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

"""Stage agents, their runs on cards, and reviewing the drafts they write."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_skill import AgentType
from app.models.board_agent import BoardAgentRunStatus, BoardAgentTrigger
from app.models.board_enums import BoardCardDocKind
from app.schemas.boards.text import DocText


class StageAgentWrite(BaseModel):
    """One agent for a stage: a skill from the org's library and when it runs.

    Agents run in ``order`` (lowest first); a stage holds at most one
    ``on_enter`` agent.
    """

    model_config = ConfigDict(extra="forbid")

    skill_id: uuid.UUID
    trigger: BoardAgentTrigger
    enabled: bool = True
    order: int = Field(ge=0)


class StageAgentRead(BaseModel):
    """One of a stage's agents, with the skill it runs."""

    id: uuid.UUID
    stage_id: uuid.UUID
    skill_id: uuid.UUID
    skill_name: str
    skill_slug: str
    agent_type: AgentType
    output_kind: BoardCardDocKind
    trigger: BoardAgentTrigger
    enabled: bool
    order: int


class AgentRunRead(BaseModel):
    """One agent run on a card."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    stage_id: uuid.UUID | None
    stage_agent_id: uuid.UUID | None
    skill_id: uuid.UUID | None
    trigger: BoardAgentTrigger
    status: BoardAgentRunStatus
    job_id: str | None
    attempt: int
    result_summary: dict[str, Any] | None
    error_message: str | None
    triggered_by: uuid.UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AgentRunAccepted(BaseModel):
    """A queued run (202): follow ``job_id`` on the job socket."""

    job_id: str
    run: AgentRunRead


class CardAgents(BaseModel):
    """What a card's AI panel shows.

    ``agents`` are the switched-on agents of the card's stage (what Run
    offers); ``runs`` the card's latest runs, newest first; ``active`` the
    one going now, if any; ``ai_enabled`` the board's switch.
    """

    ai_enabled: bool
    agents: list[StageAgentRead]
    runs: list[AgentRunRead]
    active: AgentRunRead | None


class DraftAccept(BaseModel):
    """Accept a draft as the new current version, optionally edited first.

    ``base_version`` is the current version the reviewer saw (``null`` when
    there was none); a different current version is 409.
    """

    model_config = ConfigDict(extra="forbid")

    base_version: int | None
    body_md: DocText | None = None


class BoardAgentRunPayload(BaseModel):
    """The ``board_agent_run`` job's payload: everything else is read from the run row."""

    org_id: uuid.UUID
    run_id: uuid.UUID
