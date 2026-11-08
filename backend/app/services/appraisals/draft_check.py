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

"""Reading an AI draft: only lines backed by facts we hold survive (pure).

The model's text is never trusted for links or ids. A line with no
citation, an unknown id or an unknown section is dropped, as is one that
scores, compares or judges, and links are built from our own fact records
when the draft is shown.
"""

import json
import re
from collections.abc import Collection
from dataclasses import asdict, dataclass
from typing import Any

MAX_LINE_CHARS = 300
# Scoring, comparing, judging or linking: never in a draft, whatever the prompt
# was talked into. Typed text reaches the model, so this can't rest on the rules
# in the prompt alone.
_FORBIDDEN = re.compile(
    r"https?://|www\.|\bbands?\b|\bscor(e|es|ed|ing)\b|\bratings?\b|\brated\b|"
    r"\b(better|worse|stronger|weaker|faster|slower) than\b|\bcompared (to|with)\b|"
    r"\b(out|under|over)perform|\bexpectations?\b|\bpromot(e|ed|ion)\b|"
    r"\b(deserves?|should be)\b|\b(every|all) (deadlines?|goals?)\b",
    re.IGNORECASE,
)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class DraftUnreadableError(ValueError):
    """The output wasn't the JSON the prompt asked for."""


@dataclass(frozen=True)
class DraftLine:
    """One sentence and what backs it."""

    section: str
    text: str
    fact_ids: list[str]


def read_payload(output: str) -> dict[str, Any]:
    """The JSON object in a run's output, fences and chatter around it ignored."""
    text = _FENCE.sub("", output.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise DraftUnreadableError("No JSON object in the output.")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DraftUnreadableError("The JSON didn't parse.") from exc
    if not isinstance(data, dict):
        raise DraftUnreadableError("Expected a JSON object.")
    return data


def is_forbidden(text: str) -> bool:
    """The text scores, compares, judges or links."""
    return bool(_FORBIDDEN.search(text))


def _line(raw: Any, sections: Collection[str], known: Collection[str]) -> DraftLine | None:
    if not isinstance(raw, dict):
        return None
    section, text, cited = raw.get("section"), raw.get("text"), raw.get("fact_ids")
    if section not in sections or not isinstance(text, str) or not isinstance(cited, list):
        return None
    text = text.strip()
    if not text or len(text) > MAX_LINE_CHARS or not cited or _FORBIDDEN.search(text):
        return None
    if not all(isinstance(i, str) and i in known for i in cited):
        return None
    return DraftLine(section=str(section), text=text, fact_ids=list(dict.fromkeys(cited)))


def checked_lines(
    output: str, sections: Collection[str], known: Collection[str], limit: int
) -> list[DraftLine]:
    """The lines that pass the citation check, up to ``limit``."""
    raw = read_payload(output).get("lines")
    if not isinstance(raw, list):
        raise DraftUnreadableError("Expected a list of lines.")
    lines = [line for item in raw if (line := _line(item, sections, known))]
    return lines[:limit]


def as_stored(lines: list[DraftLine]) -> list[dict[str, Any]]:
    """The lines as saved in the encrypted summary."""
    return [asdict(line) for line in lines]
