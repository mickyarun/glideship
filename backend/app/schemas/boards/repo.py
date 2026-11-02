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

"""Tracked repositories a board links."""

import uuid

from pydantic import BaseModel


class BoardRepoRead(BaseModel):
    """A repository the board links; ``url`` is its GitHub page when known."""

    id: uuid.UUID
    name: str
    url: str | None


class BoardReposRead(BaseModel):
    """Every repository the board links, by name."""

    items: list[BoardRepoRead]


class RepoOption(BoardRepoRead):
    """One of the org's active repositories, and whether the board links it."""

    linked: bool


class RepoOptions(BaseModel):
    """The org's active repositories a board admin can link, by name."""

    items: list[RepoOption]
