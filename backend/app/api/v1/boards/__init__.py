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

"""The boards HTTP API: one module per area, all behind ``boards:view``."""

from fastapi import APIRouter, Depends

from app.api.v1.boards import (
    attachments,
    boards,
    cards,
    checklist,
    comments,
    docs,
    finder,
    imports,
    labels,
    members,
    prefs,
    stages,
)
from app.core.deps import require_permissions
from app.core.permissions_boards import BOARDS_VIEW

PREFIX = "/api/v1/boards"

router = APIRouter(dependencies=[Depends(require_permissions(BOARDS_VIEW))])
# ``finder`` and ``imports`` first: their fixed paths must win over ``/{key}``.
for part in (
    finder,
    imports,
    boards,
    stages,
    members,
    labels,
    prefs,
    cards,
    checklist,
    comments,
    attachments,
    docs,
):
    router.include_router(part.router, prefix=PREFIX)
