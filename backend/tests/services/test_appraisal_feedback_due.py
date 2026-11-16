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

"""When manager feedback is due, including an item that opens after its usual date."""

from datetime import date

from app.services.appraisals.feedback_open import feedback_due_from


def test_an_item_opened_on_time_is_due_the_usual_days_after_the_period() -> None:
    # October ends on the 31st; opened on Monday 2 Nov, due 10 days after the period.
    assert feedback_due_from(date(2026, 10, 31), date(2026, 11, 2), 10) == date(2026, 11, 10)
    # Opened on the usual due date itself, it is still due that day.
    assert feedback_due_from(date(2026, 10, 31), date(2026, 11, 10), 10) == date(2026, 11, 10)


def test_an_item_opened_late_gets_a_fresh_window_instead_of_being_overdue() -> None:
    # A cycle opened on 16 Nov, so October's item opens after 10 Nov.
    assert feedback_due_from(date(2026, 10, 31), date(2026, 11, 16), 10) == date(2026, 11, 26)
    assert feedback_due_from(date(2026, 10, 31), date(2026, 11, 11), 10) == date(2026, 11, 21)
