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

"""The boards permission category and its default grants."""

from __future__ import annotations

from app.core.permissions import ALL_PERMISSION_IDS, PERMISSION_CATEGORIES
from app.core.permissions_boards import BOARDS_CREATE, BOARDS_MANAGE, BOARDS_VIEW
from app.core.role_defs import DEFAULT_SYSTEM_ROLES, UNASSIGNED_MEMBER_PERMISSIONS


def _holders(permission: str) -> set[str]:
    return {r.name for r in DEFAULT_SYSTEM_ROLES if permission in r.permission_ids}


def test_boards_category_is_last_and_backfills_view() -> None:
    assert PERMISSION_CATEGORIES[-1].key == "BOARDS"
    perms = {p.resource_id: p for p in PERMISSION_CATEGORIES[-1].permissions}
    assert set(perms) == {BOARDS_VIEW, BOARDS_CREATE, BOARDS_MANAGE}
    assert perms[BOARDS_VIEW].backfill_custom_roles
    assert not perms[BOARDS_CREATE].backfill_custom_roles
    assert not perms[BOARDS_MANAGE].backfill_custom_roles
    assert {BOARDS_VIEW, BOARDS_CREATE, BOARDS_MANAGE} <= ALL_PERMISSION_IDS


def test_every_default_role_can_view_boards() -> None:
    assert _holders(BOARDS_VIEW) == {r.name for r in DEFAULT_SYSTEM_ROLES}
    assert BOARDS_VIEW in UNASSIGNED_MEMBER_PERMISSIONS


def test_board_creation_and_management_grants() -> None:
    assert _holders(BOARDS_CREATE) == {
        "org_owner",
        "admin",
        "pm",
        "manager",
        "tech_lead",
        "designer",
    }
    assert _holders(BOARDS_MANAGE) == {"org_owner", "admin"}
