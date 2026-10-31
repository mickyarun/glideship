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

"""The words of one person's due reminder (pure, no I/O).

Overdue cards come first, then the ones due today, soonest first in each,
up to ``max_cards`` in all; the rest are counted as "and N more".
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, tzinfo

from app.repositories.board_due import DueCard
from app.services.boards.card_notify import card_path
from app.services.boards.reads import card_key
from app.services.slack_mrkdwn import escape_mrkdwn

BOARDS_PATH = "/boards"


@dataclass(frozen=True)
class DueMessage:
    """The in-app title and line, and the Slack text."""

    title: str
    message: str
    slack_text: str


def split_due(
    cards: Sequence[DueCard], day_start: datetime
) -> tuple[list[DueCard], list[DueCard]]:
    """``(overdue, due today)``: overdue means due before the local day began."""
    overdue = [c for c in cards if c.due_at < day_start]
    return overdue, [c for c in cards if c.due_at >= day_start]


def _count(n: int, what: str) -> str:
    return f"{n} {'card' if n == 1 else 'cards'} {what}"


def _line(card: DueCard, base_url: str, zone: tzinfo, overdue: bool) -> str:
    url = f"{base_url}{card_path(card.board_key, card.number)}"
    line = (
        f"• <{url}|{card_key(card.board_key, card.number)}> {escape_mrkdwn(card.title)}"
        f" · {escape_mrkdwn(card.board_name)}"
    )
    if overdue:
        line += f" · due {card.due_at.astimezone(zone).strftime('%-d %b')}"
    return line


def compose_due(
    cards: Sequence[DueCard],
    *,
    day_start: datetime,
    zone: tzinfo,
    max_cards: int,
    base_url: str,
) -> DueMessage:
    """One person's reminder for their ``cards`` (at least one)."""
    overdue, today = split_due(cards, day_start)
    parts = [_count(len(overdue), "overdue")] if overdue else []
    if today:
        parts.append(_count(len(today), "due today"))
    summary = " and ".join(parts)
    lines = ["*Your cards due today and overdue*"]
    budget = max_cards
    for heading, group, late in (("Overdue", overdue, True), ("Due today", today, False)):
        shown = group[: max(budget, 0)]
        budget -= len(shown)
        if shown:
            lines.append(f"*{heading}*")
            lines.extend(_line(card, base_url, zone, late) for card in shown)
    hidden = len(cards) - max_cards
    if hidden > 0:
        lines.append(f"_…and {hidden} more_")
    lines.append(f"<{base_url}{BOARDS_PATH}|Open boards>")
    return DueMessage(
        title="Cards due",
        message=f"You have {summary}.",
        slack_text="\n".join(lines),
    )
