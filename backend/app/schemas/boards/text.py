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

"""Text field types shared by the board schemas.

Names, titles and bodies are trimmed before their length is checked, so a
value of only spaces is refused rather than stored empty. Lengths come
from the column sizes or, for free text, from ``BoardsConfig``.
"""

from typing import Annotated

from pydantic import Field, StringConstraints

from app.config import settings
from app.models.board import BOARD_NAME_LENGTH, LABEL_NAME_LENGTH, STAGE_NAME_LENGTH
from app.models.board_card import CARD_TITLE_LENGTH

_limits = settings.boards


def _trimmed(max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


BoardName = Annotated[str, _trimmed(BOARD_NAME_LENGTH)]
StageName = Annotated[str, _trimmed(STAGE_NAME_LENGTH)]
LabelName = Annotated[str, _trimmed(LABEL_NAME_LENGTH)]
CardTitle = Annotated[str, _trimmed(CARD_TITLE_LENGTH)]
CommentText = Annotated[str, _trimmed(_limits.comment_max_chars)]
ChecklistText = Annotated[str, _trimmed(_limits.checklist_text_max_chars)]
Description = Annotated[str, Field(max_length=_limits.description_max_chars)]
DocText = Annotated[str, Field(max_length=_limits.doc_max_chars)]

# How long a card search or switcher query may be.
SEARCH_MAX_LENGTH = _limits.search_max_chars
