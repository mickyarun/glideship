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
