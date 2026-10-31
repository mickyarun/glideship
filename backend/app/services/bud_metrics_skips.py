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


"""Which BUD phases a board handover skipped, so learning metrics don't score them.

Split out of :mod:`app.services.bud_metrics_phases` to keep that module small.
"""

from datetime import datetime

from app.models.bud import BUDStatus


def skipped_by_handover(events: list[tuple[str, datetime, bool]]) -> set[str]:
    """Phases a board handover only ever stepped through.

    A handover writes one ``status_change`` per stage it skips, tagged
    ``via: handover`` and all at once, so the phase each one leaves lasted
    no time. Its drift would read as "finished early"; those phases keep
    their (zero) window but report no drift.

    A phase counts only when every time the BUD left it, a handover step
    did. A BUD sent back and handed over again walks from ``bud`` once
    more (the restore and the steps are tagged too), and that walk can
    pass a phase the team really worked in on the first pass. Such a phase
    was also left some other way (a move by hand, the discard that sent it
    back), so it keeps its drift.
    """
    by_handover: set[str] = set()
    otherwise: set[str] = set()
    current = BUDStatus.BUD.value
    for to_phase, _at, via_handover in events:
        if to_phase == current:
            continue
        (by_handover if via_handover else otherwise).add(current)
        current = to_phase
    return by_handover - otherwise
