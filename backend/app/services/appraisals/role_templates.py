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

"""Role templates: seeding an org's set and matching a person to one."""

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.schemas.appraisal_role_template import SeedTemplate

SEED_FILE = Path(__file__).with_name("role_templates_seed.json")


@lru_cache(maxsize=1)
def seed_templates() -> tuple[SeedTemplate, ...]:
    """The seeded templates, validated once."""
    raw = json.loads(SEED_FILE.read_text())
    return tuple(TypeAdapter(list[SeedTemplate]).validate_python(raw))


async def ensure_seeded(
    db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID | None
) -> list[AppraisalRoleTemplate]:
    """The org's templates, seeding the standard set the first time.

    Only seeds an org with none at all, so a template HR deleted on purpose
    never comes back (the general fallback can't be deleted).
    """
    repo = AppraisalRoleTemplateRepository(db, org_id=org_id)
    existing = await repo.list_for_org()
    if existing:
        return existing
    # The general fallback can't be deleted, so an org that has ever been
    # seeded always has one. Lock before seeding so two callers can't both.
    await AppraisalCycleRepository(db, org_id=org_id).lock_org()
    existing = await repo.list_for_org()
    if existing:
        return existing
    for seed in seed_templates():
        db.add(
            AppraisalRoleTemplate(
                org_id=org_id,
                updated_by=actor_id,
                **seed.model_dump(mode="json"),
            )
        )
    await db.flush()
    return await repo.list_for_org()


def _words(text: str | None) -> list[str]:
    return re.findall(r"[a-z0-9&]+", (text or "").lower())


def _designation_hit(title: list[str], terms: Sequence[str]) -> tuple[int, int] | None:
    """Where the earliest of ``terms`` appears in ``title`` as whole words.

    Returns (position, -length) so the earliest, then the longest, sorts
    first: "QA Engineer" is QA, "Support Engineer" is Support.
    """
    best: tuple[int, int] | None = None
    for term in terms:
        words = _words(term)
        if not words:
            continue
        for i in range(len(title) - len(words) + 1):
            if title[i : i + len(words)] == words:
                hit = (i, -len(words))
                best = hit if best is None or hit < best else best
                break
    return best


def match_template(
    templates: Sequence[AppraisalRoleTemplate],
    department: str | None,
    designation: str | None,
    overrides: Mapping[str, str] | None = None,
) -> AppraisalRoleTemplate | None:
    """The template for a person (pure).

    In order: a cycle override for their department or designation, an
    exact department match, the designation term that comes first in their
    title, then the general fallback. None only when the org has no
    fallback, which the cycle's readiness check reports.
    """
    by_id = {str(t.id): t for t in templates}
    for key in (department, designation):
        chosen = by_id.get((overrides or {}).get(key or "", ""))
        if chosen is not None:
            return chosen
    dept = _words(department)
    for template in templates:
        if dept and dept in [_words(d) for d in template.match_departments]:
            return template
    title = _words(designation)
    hits = [
        (hit, template.name, template)
        for template in templates
        if (hit := _designation_hit(title, template.match_designations)) is not None
    ]
    if hits:
        return min(hits, key=lambda h: (h[0], h[1]))[2]
    return next((t for t in templates if t.is_default), None)
