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

"""What a handover confirm writes into its BUD: the card's draft with the dialog's edits."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.bud import BUDStatus
from app.repositories.board_repo import BoardRepoRepository
from app.schemas.boards.handover import HandoverConfirm, HandoverOverrides, ImpactedRepo
from app.schemas.bud import BUDCreate
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardRuleError
from app.services.boards.handover_content import draft_for, impacted, without_board_section
from app.services.boards.handover_rules import check_requirements, target_of

UNKNOWN_REPOS = "Pick repositories from the organisation's active ones."


async def _repos(
    db: AsyncSession, access: BoardAccess, drafted: list[ImpactedRepo], o: HandoverOverrides
) -> list[ImpactedRepo]:
    if o.impacted_repo_ids is None:
        return drafted
    wanted = list(dict.fromkeys(o.impacted_repo_ids))
    found = await BoardRepoRepository(db, org_id=access.org_id).active_among(wanted)
    if len(found) != len(wanted):
        raise BoardRuleError(UNKNOWN_REPOS)
    return impacted(found)


@dataclass(frozen=True)
class PreparedBUD:
    """What a confirm writes into the BUD: the create body, its repositories and target."""

    create: BUDCreate
    repos: list[ImpactedRepo]
    target: BUDStatus

    @property
    def impacted_repos_json(self) -> list[dict[str, Any]] | None:
        """The repositories as ``bud_documents.impacted_repos`` stores them."""
        return [repo.model_dump(mode="json") for repo in self.repos] or None


async def prepare(
    db: AsyncSession, access: BoardAccess, card: BoardCard, body: HandoverConfirm
) -> PreparedBUD:
    """The card's draft with the dialog's edits, checked for the landing it asks for.

    Raises:
        HandoverNeedsRequirementsError: A tech-plan landing with nothing to plan from.
        BoardRuleError: An overridden repository isn't one of the org's active ones.
    """
    draft = await draft_for(db, access, card)
    o = body.overrides or HandoverOverrides()
    title = o.title or draft.title
    requirements = draft.requirements_md if o.requirements_md is None else o.requirements_md
    target = target_of(access, body)
    # An edited text still carries the generated section; only what's above it counts.
    source = draft.source_md if o.requirements_md is None else without_board_section(requirements)
    check_requirements(target, source)
    repos = await _repos(db, access, draft.impacted_repos, o)
    create = BUDCreate(
        title=title,
        requirements_md=requirements or None,
        priority=draft.priority,
        figma_url=draft.figma_url,
        auto_generate_phases={s.value: on for s, on in body.auto_generate_phases.items()},
        stage_skill_overrides=body.stage_skill_overrides,
    )
    return PreparedBUD(create=create, repos=repos, target=target)
