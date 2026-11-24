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

"""What someone is told when a request goes past a "stops at balance" type."""

from decimal import Decimal

from app.models.leave_type import LeaveType
from app.services.leave.balances import BalanceLine
from app.services.leave.over_balance import Other, over_balance_message, refusal

D = Decimal


def test_some_left_points_at_what_else_they_have() -> None:
    text = over_balance_message("Sick leave", D(1), [Other("Earned leave", D(6))])
    assert text == (
        "You have 1 day of Sick leave left, so request that much. "
        "Request the rest as another type: Earned leave (6 days left)."
    )


def test_none_left_and_types_that_are_used_up_are_not_offered() -> None:
    others = [Other("Earned leave", D(0)), Other("Unpaid leave", None)]
    assert over_balance_message("Sick leave", D(0), others) == (
        "You have no Sick leave left. Request it as another type: Unpaid leave."
    )


def _line(name: str, left: Decimal, *, stops: bool = False) -> BalanceLine:
    return BalanceLine(
        leave_type=LeaveType(name=name, stops_at_balance=stops),
        allocated=D(5),
        earned=D(5),
        adjustments=D(0),
        used=D(5) - left,
        pending=D(0),
        available=left,
        taken=D(0),
    )


def test_nothing_else_left_goes_through_as_loss_of_pay() -> None:
    sick = _line("Sick leave", D(0), stops=True)
    lines = [sick, _line("Earned leave", D(0))]
    assert refusal(sick.leave_type, D(3), sick, lines) is None


def test_another_type_with_leave_left_still_refuses() -> None:
    sick = _line("Sick leave", D(0), stops=True)
    lines = [sick, _line("Earned leave", D("2.5"))]
    why = refusal(sick.leave_type, D(3), sick, lines)
    assert why is not None and "Earned leave (2.5 days left)" in why
