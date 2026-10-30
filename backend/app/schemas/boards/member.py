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

"""People and teams holding a role on a board."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.board_enums import BoardMemberRole


class RoleBody(BaseModel):
    """The role to give a person or team on the board."""

    model_config = ConfigDict(extra="forbid")

    role: BoardMemberRole


class MemberRead(BaseModel):
    """A person's own role on the board."""

    user_id: uuid.UUID
    name: str
    avatar_url: str | None
    role: BoardMemberRole


class TeamGrantRead(BaseModel):
    """A team's role on the board."""

    team_id: uuid.UUID
    name: str
    role: BoardMemberRole


class MembersRead(BaseModel):
    """Everyone granted a role on the board, individually or through a team."""

    members: list[MemberRead]
    teams: list[TeamGrantRead]


class TeamOption(BaseModel):
    """A team in the org that could be given a role on the board."""

    id: uuid.UUID
    name: str
    member_count: int


class TeamOptions(BaseModel):
    """The org's active teams, by name, for a board admin's team picker."""

    items: list[TeamOption]
