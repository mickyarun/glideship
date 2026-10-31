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

"""Per-BUD stage skill picks: check each one, then store them."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.skill_mapping import BUD_STAGE_AGENT_TYPE
from app.models.bud import BUDStatus
from app.repositories.agent_skill import AgentSkillRepository
from app.repositories.bud_stage_skill_override import BUDStageSkillOverrideRepository


class StageSkillOverrideError(ValueError):
    """A stage can't take the picked skill; the message says why (sent as a 400)."""


async def persist_stage_skill_overrides(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud_id: uuid.UUID,
    overrides: dict[BUDStatus, uuid.UUID],
) -> None:
    """Validate then store per-stage skill picks for one BUD.

    Each ``skill_id`` must (a) belong to the caller's org and (b) have
    the correct ``agent_type`` for the stage it's being assigned to —
    e.g. picking a ``design`` skill for the ``testing`` stage is refused.

    Raises:
        StageSkillOverrideError: A stage isn't configurable, the skill is
            missing, or it runs a different agent than the stage does.
    """
    skill_repo = AgentSkillRepository(db, org_id=org_id)

    for stage, skill_id in overrides.items():
        expected_agent_type = BUD_STAGE_AGENT_TYPE.get(stage)
        if expected_agent_type is None:
            raise StageSkillOverrideError(f"Stage '{stage.value}' is not configurable")
        skill = await skill_repo.get_by_id(skill_id)
        if skill is None:
            raise StageSkillOverrideError(f"Skill {skill_id} not found for stage {stage.value}")
        if skill.agent_type != expected_agent_type:
            raise StageSkillOverrideError(
                f"Skill {skill.skill_slug!r} (agent_type={skill.agent_type.value}) "
                f"cannot be assigned to stage {stage.value}; that stage runs the "
                f"{expected_agent_type.value} agent."
            )

    override_repo = BUDStageSkillOverrideRepository(db, org_id=org_id)
    await override_repo.bulk_set_for_bud(bud_id, overrides)
