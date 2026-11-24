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

A manager "rates high" when two in three or more of their final bands are
an Exceeded band, on a team of three or more, while every other manager's
reviews together are under one in two. A pattern needs others to stand
out from: a team that rates that high before any other manager's reviews
are in is "waiting to compare", held like one that rates high, until
another team's reviews arrive and the rule above can run.
"""

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.services.appraisals.review_rules import HIGH_BANDS

FLAG_TEAM = 3
CHANGED_MOST = 0.8
HIGH_SHARE = 2 / 3
OTHERS_SHARE = 0.5


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
            flag = "Kept every person's own rating."
        elif 1 - agreement >= CHANGED_MOST:
            flag = "Changed nearly every person's rating."
    return TeamFigures(
        bands={b: bands.get(b, 0) for b in range(1, 6)}, agreement=agreement, gaps=gaps, flag=flag
    )


@dataclass(frozen=True)
class HighShare:
    """How many of a manager's final bands are Exceeded, and of how many."""

    high: int
    people: int


def high_share(people: Sequence[Scored]) -> HighShare:
    """One manager's count of Exceeded bands."""
    return HighShare(sum(p.final_band in HIGH_BANDS for p in people), len(people))


def others(teams: Mapping[uuid.UUID, HighShare], manager: uuid.UUID) -> HighShare:
    """Every other manager's reviews together."""
    rest = [t for key, t in teams.items() if key != manager]
    return HighShare(sum(t.high for t in rest), sum(t.people for t in rest))


def rates_high(teams: Mapping[uuid.UUID, HighShare]) -> set[uuid.UUID]:
    """Managers whose share of Exceeded bands stands out from everyone else's."""
    out = set()
    for manager, team in teams.items():
        rest = others(teams, manager)
        if team.people < FLAG_TEAM or rest.people == 0:
            continue
        if team.high / team.people >= HIGH_SHARE and rest.high / rest.people < OTHERS_SHARE:
            out.add(manager)
    return out


def waiting_to_compare(teams: Mapping[uuid.UUID, HighShare]) -> set[uuid.UUID]:
    """Teams that rate high on their own with no other manager's reviews in yet."""
    return {
        manager
        for manager, team in teams.items()
        if team.people >= FLAG_TEAM
        and team.high / team.people >= HIGH_SHARE
        and others(teams, manager).people == 0
    }
