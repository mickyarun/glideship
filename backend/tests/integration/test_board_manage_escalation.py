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

"""``boards:manage`` is an escalation permission: only holders may hand it out."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.permissions_boards import BOARDS_MANAGE
from app.models.permission import Permission
from app.repositories.role import RoleRepository
from tests.integration.auth_tenancy_support import add_user, new_tenant
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration


async def _ids(factory: Factory, *resource_ids: str) -> list[str]:
    async with factory() as db:
        rows = await db.scalars(select(Permission).where(Permission.resource_id.in_(resource_ids)))
        return [str(p.id) for p in rows]


async def _base(factory: Factory) -> str:
    async with factory() as db:
        role = await RoleRepository(db).get_by_name_system("developer")
        assert role is not None
        return str(role.id)


async def test_a_manager_cannot_grant_boards_manage(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    t = await new_tenant(pg_session_factory)
    manager_id, _ = await add_user(pg_session_factory, t.org, "manager")
    admin_id, _ = await add_user(pg_session_factory, t.org, "admin")
    manager, admin = as_user(manager_id, t.org), as_user(admin_id, t.org)
    base = await _base(pg_session_factory)
    wider = await _ids(pg_session_factory, "team:view", BOARDS_MANAGE)

    made = await client.post(
        "/api/v1/roles",
        json={"name": "Board boss", "base_role_id": base, "permission_ids": wider},
        headers=manager,
    )
    assert made.status_code == 403, made.text
    assert BOARDS_MANAGE in made.json()["detail"]

    plain = await client.post(
        "/api/v1/roles",
        json={
            "name": "Board helper",
            "base_role_id": base,
            "permission_ids": await _ids(pg_session_factory, "team:view"),
        },
        headers=manager,
    )
    assert plain.status_code == 201, plain.text
    role_url = f"/api/v1/roles/{plain.json()['id']}"
    widened = await client.put(role_url, json={"permission_ids": wider}, headers=manager)
    assert widened.status_code == 403, widened.text
    by_admin = await client.put(role_url, json={"permission_ids": wider}, headers=admin)
    assert by_admin.status_code == 200, by_admin.text
