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

"""Read-only BUD stage settings for anyone who can see BUDs.

The full settings read needs ``integrations:view``, which QA and other
members lack, yet the BUD screens need to know whether UAT is on and who
owns it (QA may move a BUD out of UAT only when the org made QA its owner).
Changing them stays on the connections settings endpoint.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_permissions
from app.models.user import User
from app.schemas.settings import BUDStageSettings
from app.services.phase_owner import org_bud_stage_settings

router = APIRouter(tags=["settings"])


@router.get(
    "/bud-stages",
    response_model=BUDStageSettings,
    response_model_by_alias=True,
    dependencies=[Depends(require_permissions("buds:view"))],
)
async def read_bud_stages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BUDStageSettings:
    """The org's BUD stage settings: whether UAT is on, and who owns it."""
    return await org_bud_stage_settings(db, current_user.org_id)
