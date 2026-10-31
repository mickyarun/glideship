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

"""Sending a BUD back to its card, and the BUD's Origin panel."""

from pydantic import BaseModel, ConfigDict

from app.schemas.boards.card_detail import CommentPage
from app.schemas.boards.handover import HandoverRead
from app.schemas.boards.text import ReturnReason


class HandoverReturn(BaseModel):
    """Why the BUD goes back to the board; posted on the card as a comment."""

    model_config = ConfigDict(extra="forbid")

    reason: ReturnReason


class OriginBoard(BaseModel):
    """The board the origin card is on now."""

    key: str
    name: str


class OriginCard(BaseModel):
    """The card a BUD was handed over from."""

    key: str
    number: int
    title: str
    board: OriginBoard


class BUDOrigin(BaseModel):
    """Where a BUD came from, for its Origin panel.

    ``card`` is null when the BUD wasn't handed over (``hidden`` false) or
    when the caller can't open the card's board (``hidden`` true; nothing
    about the board is sent). ``comments`` are the card's, newest first.
    """

    card: OriginCard | None
    hidden: bool = False
    comments: CommentPage | None = None
    handovers: list[HandoverRead] = []
