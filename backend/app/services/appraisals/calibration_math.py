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

"""Calibration figures for one manager's team (pure).

Agreement is how often the final band kept the employee's own score,
among people who self-scored. A gap is a self-score and final band two or
more apart. A team of three or more where the manager agreed with every
score, or changed four in five or more, is flagged for HR to look at.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

FLAG_TEAM = 3
CHANGED_MOST = 0.8


@dataclass(frozen=True)
class Scored:
    """One reviewed person: their self-score and the final band."""

    self_band: int | None
    final_band: int


@dataclass(frozen=True)
class TeamFigures:
    """The figures for one manager."""

    bands: dict[int, int]
    agreement: float | None
    gaps: int
    flag: str | None


def figures(people: Sequence[Scored]) -> TeamFigures:
    """Bands spread, agreement rate, big gaps and any flag."""
    bands = Counter(p.final_band for p in people)
    scored = [p for p in people if p.self_band is not None]
    kept = sum(p.self_band == p.final_band for p in scored)
    agreement = kept / len(scored) if scored else None
    gaps = sum(abs((p.self_band or p.final_band) - p.final_band) >= 2 for p in scored)
    flag = None
    if agreement is not None and len(scored) >= FLAG_TEAM:
        if agreement == 1:
            flag = "Agreed with every self-score."
        elif 1 - agreement >= CHANGED_MOST:
            flag = "Changed nearly every self-score."
    return TeamFigures(
        bands={b: bands.get(b, 0) for b in range(1, 6)}, agreement=agreement, gaps=gaps, flag=flag
    )
