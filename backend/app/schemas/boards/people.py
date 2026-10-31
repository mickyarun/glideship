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

"""Everyone who can open a board, and so can be assigned its cards."""

import uuid

from pydantic import BaseModel

from app.models.board_enums import BoardAccessVia, BoardMemberRole


class BoardPersonRead(BaseModel):
    """A person with access, their highest role and where it comes from."""

    id: uuid.UUID
    name: str
    avatar_url: str | None
    role: BoardMemberRole
    via: BoardAccessVia


class BoardPeopleRead(BaseModel):
    """Everyone with access to the board, by name."""

    items: list[BoardPersonRead]
