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

"""The org's skill library as the stage-agent picker shows it.

Any skill in the org's library can run on a stage, custom ones included.
The two board skills (``BOARD_AGENT_TYPES``) come first, flagged
``suggested``; the rest follow by name. Each names the card document its
runs write (``AGENT_OUTPUT_KINDS``).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_skill import AgentSkill
from app.repositories.agent_skill import AgentSkillRepository
from app.schemas.boards.agent import StageSkillRead
from app.services.boards.access import BoardAccess
from app.services.boards.constants import (
    AGENT_OUTPUT_KINDS,
    BOARD_AGENT_TYPES,
    DEFAULT_AGENT_OUTPUT_KIND,
)


def _read(skill: AgentSkill) -> StageSkillRead:
    return StageSkillRead(
        id=skill.id,
        name=skill.name,
        slug=skill.skill_slug,
        agent_type=skill.agent_type,
        suggested=skill.agent_type in BOARD_AGENT_TYPES,
        output_kind=AGENT_OUTPUT_KINDS.get(skill.agent_type, DEFAULT_AGENT_OUTPUT_KIND),
    )


def _order(skill: AgentSkill) -> tuple[int, str, str]:
    suggested = list(BOARD_AGENT_TYPES)
    rank = suggested.index(skill.agent_type) if skill.agent_type in suggested else len(suggested)
    return rank, skill.name.lower(), str(skill.id)


async def stage_skills(db: AsyncSession, access: BoardAccess) -> list[StageSkillRead]:
    """Every skill in the org's library, the suggested board skills first."""
    skills = await AgentSkillRepository(db, org_id=access.org_id).list_all_sorted()
    return [_read(s) for s in sorted(skills, key=_order)]
