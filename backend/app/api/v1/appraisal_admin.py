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

"""HR's appraisal setup: org settings and role templates (cycles: :mod:`.appraisal_cycles`).

Every route needs ``appraisals:manage``.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.core.permission_deps import require_permissions
from app.core.permissions_people import APPRAISALS_MANAGE
from app.schemas.appraisal_role_template import RoleTemplateBody, RoleTemplateRead
from app.schemas.appraisal_settings import AppraisalSettings
from app.services.appraisals import role_template_admin
from app.services.appraisals.context import Caller
from app.services.appraisals.role_templates import ensure_seeded
from app.services.appraisals.settings import load_appraisal_settings, save_appraisal_settings

router = APIRouter(
    tags=["appraisals"], dependencies=[Depends(require_permissions(APPRAISALS_MANAGE))]
)


@router.get("/settings", response_model=AppraisalSettings)
async def get_settings(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> AppraisalSettings:
    """The org's appraisal settings."""
    return await load_appraisal_settings(db, caller.org_id)


@router.put("/settings", response_model=AppraisalSettings)
async def put_settings(
    body: AppraisalSettings,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalSettings:
    """Save the org's settings; running cycles keep their own copy."""
    await save_appraisal_settings(db, caller.org_id, body)
    return body


@router.get("/role-templates", response_model=list[RoleTemplateRead])
async def list_templates(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[RoleTemplateRead]:
    """The org's role templates, seeding the standard set the first time."""
    rows = await ensure_seeded(db, caller.org_id, caller.user_id)
    return [RoleTemplateRead.model_validate(t) for t in rows]


@router.post("/role-templates", response_model=RoleTemplateRead, status_code=201)
async def post_template(
    body: RoleTemplateBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> RoleTemplateRead:
    """A new role template."""
    template = await role_template_admin.create_template(db, caller.org_id, caller.user_id, body)
    return RoleTemplateRead.model_validate(template)


@router.put("/role-templates/{template_id}", response_model=RoleTemplateRead)
async def put_template(
    template_id: uuid.UUID,
    body: RoleTemplateBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> RoleTemplateRead:
    """Replace a role template's contents."""
    template = await role_template_admin.update_template(
        db, caller.org_id, caller.user_id, template_id, body
    )
    return RoleTemplateRead.model_validate(template)


@router.delete("/role-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a role template (not the general fallback)."""
    await role_template_admin.delete_template(db, caller.org_id, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
