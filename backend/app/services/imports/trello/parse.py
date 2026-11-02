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


"""Reading a Trello board's JSON (export or API read), once.

The raw JSON is read exactly once, when the import is created (or the API
snapshot is fetched): array sizes are counted against the
``BoardsConfig.import_max_*`` caps before any model is built, then the
board is validated and stored in its compact form, comments only and
nothing the import drops. Discovery and the run read that compact form.
"""

import json
from typing import Any

from pydantic import ValidationError

from app.config import settings
from app.services.imports.errors import ImportSourceDataError
from app.services.imports.trello.models import TrelloExport

NOT_A_BOARD = (
    "This isn't a Trello board export. Export the board as JSON from Trello and try again."
)
TOO_BIG = "This board is too big to import here: it has more than {cap:,} {what}."
# Errors a decoder or validator raises on hostile input (too deep, huge numbers).
_UNREADABLE = (ValueError, RecursionError)


def parse_export(data: bytes) -> TrelloExport:
    """Read an uploaded export, refusing anything that isn't shaped like a Trello board.

    Raises:
        ImportSourceDataError: Not JSON, not a board, or over a count cap.
    """
    try:
        raw = json.loads(data)
    except _UNREADABLE as exc:
        raise ImportSourceDataError(NOT_A_BOARD) from exc
    return parse_board(raw)


def parse_board(raw: Any) -> TrelloExport:
    """Already-decoded board JSON as its compact model; see :func:`parse_export`."""
    if not isinstance(raw, dict) or "lists" not in raw or "cards" not in raw:
        raise ImportSourceDataError(NOT_A_BOARD)
    check_counts(raw)
    try:
        export = TrelloExport.model_validate(raw)
    except (ValidationError, *_UNREADABLE) as exc:
        raise ImportSourceDataError(NOT_A_BOARD) from exc
    return export.model_copy(
        update={"actions": export.comments(), "action_total": export.action_count}
    )


def check_counts(raw: dict[str, Any]) -> None:
    """Refuse a board whose arrays pass the import caps, before anything is built."""
    cfg = settings.boards
    caps = (
        ("cards", cfg.import_max_cards),
        ("actions", cfg.import_max_actions),
        ("lists", cfg.import_max_lists),
        ("members", cfg.import_max_members),
        ("labels", cfg.import_max_labels),
        ("checklists", cfg.import_max_checklists),
    )
    for key, cap in caps:
        if _length(raw.get(key)) > cap:
            raise ImportSourceDataError(TOO_BIG.format(cap=cap, what=key))
    checklists = raw.get("checklists")
    lines = sum(_length(c.get("checkItems")) for c in _list(checklists) if isinstance(c, dict))
    if lines > cfg.import_max_check_items:
        cap = cfg.import_max_check_items
        raise ImportSourceDataError(TOO_BIG.format(cap=cap, what="checklist items"))


def compact_json(export: TrelloExport) -> bytes:
    """The compact form stored for the session (non-numeric positions become null)."""
    return export.model_dump_json(by_alias=True).encode()


def load_compact(data: bytes) -> TrelloExport:
    """The stored compact form; it was validated when it was written."""
    try:
        return TrelloExport.model_validate_json(data)
    except (ValidationError, *_UNREADABLE) as exc:
        raise ImportSourceDataError(NOT_A_BOARD) from exc


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _length(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0
