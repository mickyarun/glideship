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

"""The caller's appraisal to-do list: it feeds the home page and the nav badge."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.schemas.appraisal_todo import TodoItem
from app.services.appraisals.context import Caller
from app.services.appraisals.todo import todo_list

router = APIRouter(tags=["appraisals"])


@router.get("/todo", response_model=list[TodoItem])
async def get_todo(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[TodoItem]:
    """What the caller has to do now: their own, their team's and, for HR, the cycles'."""
    return await todo_list(db, caller)
