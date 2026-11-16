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

"""Whether an appraisal gets AI drafts: three switches, any manual wins (pure).

The result is saved on each appraisal when the cycle opens, so flipping a
switch later never moves a running cycle.
"""

from app.models.appraisal_enums import DraftingMode


def drafting_mode(*, org_ai: bool, cycle_ai: bool, template_ai: bool) -> DraftingMode:
    """AI only when the org, the cycle and the person's role template all allow it."""
    return DraftingMode.AI if org_ai and cycle_ai and template_ai else DraftingMode.MANUAL
