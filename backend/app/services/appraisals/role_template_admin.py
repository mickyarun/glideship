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

"""HR's edits to role templates."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.schemas.appraisal_role_template import RoleTemplateBody
from app.services.appraisals.errors import (
    AppraisalConflictError,
    AppraisalNotFoundError,
)

TAKEN = "Another template already has that name."


async def get_template(
    db: AsyncSession, org_id: uuid.UUID, template_id: uuid.UUID
) -> AppraisalRoleTemplate:
    """The org's template, or "not found"."""
    template = await AppraisalRoleTemplateRepository(db, org_id=org_id).get_by_id(template_id)
    if template is None:
        raise AppraisalNotFoundError("Role template not found.")
    return template


async def create_template(
    db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID, body: RoleTemplateBody
) -> AppraisalRoleTemplate:
    """A new template."""
    repo = AppraisalRoleTemplateRepository(db, org_id=org_id)
    if await repo.get_by_name(body.name) is not None:
        raise AppraisalConflictError(TAKEN)
    template = AppraisalRoleTemplate(
        org_id=org_id, updated_by=actor_id, **body.model_dump(mode="json")
    )
    return await repo.create(template)


async def update_template(
    db: AsyncSession,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    template_id: uuid.UUID,
    body: RoleTemplateBody,
) -> AppraisalRoleTemplate:
    """Replace a template's contents. Enrolled appraisals keep pointing at it."""
    template = await get_template(db, org_id, template_id)
    clash = await AppraisalRoleTemplateRepository(db, org_id=org_id).get_by_name(body.name)
    if clash is not None and clash.id != template.id:
        raise AppraisalConflictError(TAKEN)
    for field, value in body.model_dump(mode="json").items():
        setattr(template, field, value)
    template.updated_by = actor_id
    await db.flush()
    return template


async def delete_template(db: AsyncSession, org_id: uuid.UUID, template_id: uuid.UUID) -> None:
    """Delete a template; the general fallback stays."""
    template = await get_template(db, org_id, template_id)
    if template.is_default:
        raise AppraisalConflictError("The general template is the fallback and can't be deleted.")
    await AppraisalRoleTemplateRepository(db, org_id=org_id).delete(template)
