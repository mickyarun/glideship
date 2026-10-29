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

"""SQL predicates over ``org_to_user`` memberships."""

from sqlalchemy import ColumnElement, and_, false, or_, select, true

from app.core.role_defs import UNASSIGNED_MEMBER_PERMISSIONS
from app.models.permission import Permission
from app.models.role import Role, RolePermission, RoleScopeType
from app.models.user import OrgToUser, UserRole


def membership_holds(permission: str) -> ColumnElement[bool]:
    """SQL predicate: the ``OrgToUser`` row's role grants ``permission``.

    Correlates on ``OrgToUser.role_id`` from the enclosing query. The
    system ``org_owner`` role holds every permission.
    """
    holds = (
        select(RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            RolePermission.role_id == OrgToUser.role_id,
            Permission.resource_id == permission,
        )
        .exists()
    )
    is_owner = (
        select(Role.id)
        .where(
            Role.id == OrgToUser.role_id,
            Role.scope_type == RoleScopeType.SYSTEM,
            Role.name == UserRole.ORG_OWNER.value,
        )
        .exists()
    )
    # Role-less memberships resolve to the unassigned-member set, the same
    # rule ``permission_deps.permissions_for_role`` applies in Python.
    unassigned = and_(
        OrgToUser.role_id.is_(None),
        true() if permission in UNASSIGNED_MEMBER_PERMISSIONS else false(),
    )
    return or_(holds, is_owner, unassigned)
