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

"""Field types shared by the board schemas.

Names, titles and bodies are trimmed before their length is checked, so a
value of only spaces is refused rather than stored empty. A card
description of only spaces means no description and becomes ``None``. Lengths come
from the column sizes or the product limits in ``services/boards/constants``.
"""

import uuid
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

from app.models.board import BOARD_NAME_LENGTH, LABEL_NAME_LENGTH, STAGE_NAME_LENGTH
from app.models.board_card import CARD_TITLE_LENGTH, blank_as_null
from app.services.boards.constants import (
    BOARD_DESCRIPTION_MAX_CHARS,
    CARD_DESCRIPTION_MAX_CHARS,
    CARD_DOC_MAX_CHARS,
    CHECKLIST_MAX_ITEMS,
    CHECKLIST_TEXT_MAX_CHARS,
    COMMENT_MAX_CHARS,
    HANDOVER_RETURN_REASON_MAX_CHARS,
    ID_LIST_MAX_ITEMS,
    SEARCH_MAX_CHARS,
)


def _trimmed(max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


BoardName = Annotated[str, _trimmed(BOARD_NAME_LENGTH)]
StageName = Annotated[str, _trimmed(STAGE_NAME_LENGTH)]
LabelName = Annotated[str, _trimmed(LABEL_NAME_LENGTH)]
CardTitle = Annotated[str, _trimmed(CARD_TITLE_LENGTH)]
CommentText = Annotated[str, _trimmed(COMMENT_MAX_CHARS)]
ReturnReason = Annotated[str, _trimmed(HANDOVER_RETURN_REASON_MAX_CHARS)]
ChecklistText = Annotated[str, _trimmed(CHECKLIST_TEXT_MAX_CHARS)]
BoardDescription = Annotated[str, Field(max_length=BOARD_DESCRIPTION_MAX_CHARS)]
Description = Annotated[str, Field(max_length=CARD_DESCRIPTION_MAX_CHARS)]
CardDescription = Annotated[Description | None, AfterValidator(blank_as_null)]
DocText = Annotated[str, Field(max_length=CARD_DOC_MAX_CHARS)]
IdList = Annotated[list[uuid.UUID], Field(max_length=ID_LIST_MAX_ITEMS)]
OrderList = Annotated[list[uuid.UUID], Field(min_length=1, max_length=ID_LIST_MAX_ITEMS)]
ChecklistOrderList = Annotated[
    list[uuid.UUID], Field(min_length=1, max_length=CHECKLIST_MAX_ITEMS)
]

SEARCH_MAX_LENGTH = SEARCH_MAX_CHARS
