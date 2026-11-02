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

"""Gap-based positions: a new place is the midpoint of its neighbours.

Positions are float8 ``position_gap`` apart. When the space between two
neighbours drops below ``position_epsilon`` there is no safe midpoint, and
the stage is respaced before trying again.
"""

from app.config import settings


def position_between(lo: float | None, hi: float | None) -> float | None:
    """A position strictly between ``lo`` and ``hi`` (None means no neighbour that side).

    Returns None when the neighbours are too close to split, so the caller
    rebalances the stage and asks again.
    """
    gap, epsilon = settings.boards.position_gap, settings.boards.position_epsilon
    if lo is None and hi is None:
        return gap
    if lo is None:
        assert hi is not None
        return hi - gap
    if hi is None:
        return lo + gap
    if hi - lo < epsilon:
        return None
    return (lo + hi) / 2
