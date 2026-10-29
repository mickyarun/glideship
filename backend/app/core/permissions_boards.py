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

"""Permission category for boards, appended after the people categories.

These gate the boards area as a whole. What someone may do on one board is
their per-board role, resolved by
:class:`app.repositories.board_access.BoardAccessRepository`.
"""

from types import MappingProxyType
from typing import Final

from app.core.permission_types import CategoryDef, PermissionDef

BOARDS_VIEW = "boards:view"
BOARDS_CREATE = "boards:create"
BOARDS_MANAGE = "boards:manage"

BOARD_PERMISSION_CATEGORIES: list[CategoryDef] = [
    CategoryDef(
        key="BOARDS",
        name="Boards",
        description="Team boards with their own stages, members and cards",
        permissions=[
            PermissionDef(
                BOARDS_VIEW,
                "View Boards",
                "Open the boards area and see boards visible to the whole org",
                backfill_custom_roles=True,
            ),
            PermissionDef(
                BOARDS_CREATE, "Create Boards", "The creator becomes the new board's admin"
            ),
            PermissionDef(
                BOARDS_MANAGE,
                "Manage All Boards",
                "Admin on every board, including members-only ones",
            ),
        ],
    ),
]

_VIEW_ONLY: Final = (BOARDS_VIEW,)
_VIEW_CREATE: Final = (BOARDS_VIEW, BOARDS_CREATE)

# Board permissions each default system role gets on top of its own specs;
# ``org_owner`` already holds everything.
BOARD_ROLE_GRANTS: Final = MappingProxyType(
    {
        "admin": (BOARDS_VIEW, BOARDS_CREATE, BOARDS_MANAGE),
        "pm": _VIEW_CREATE,
        "manager": _VIEW_CREATE,
        "tech_lead": _VIEW_CREATE,
        "designer": _VIEW_CREATE,
        "quiz_master": _VIEW_ONLY,
        "developer": _VIEW_ONLY,
        "qa": _VIEW_ONLY,
        "support": _VIEW_ONLY,
        "viewer": _VIEW_ONLY,
        "hr": _VIEW_ONLY,
        "sales": _VIEW_ONLY,
    }
)
