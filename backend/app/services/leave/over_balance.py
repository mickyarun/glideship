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

"""Why a request past a "stops at balance" type's balance is refused (pure).

Sick leave, usually: rather than the extra days quietly becoming loss of
pay, the person is told what's left and pointed at the leave they still
have, so they can split the request themselves. With no other leave left
there is nothing to point at, so the days go through as loss of pay.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.models.leave_type import LeaveType
from app.services.leave.balances import BalanceLine

ZERO = Decimal("0")


@dataclass(frozen=True)
class Other:
    """Another leave type the person could use instead; None left = no limit."""

    name: str
    left: Decimal | None


def _days(days: Decimal) -> str:
    value = f"{days.normalize():f}"
    return f"{value} day" if days == 1 else f"{value} days"


def usable_others(others: Sequence[Other]) -> list[Other]:
    """The other types they could still take leave from."""
    return [o for o in others if o.left is None or o.left > ZERO]


def over_balance_message(type_name: str, left: Decimal, others: Sequence[Other]) -> str:
    """E.g. "You have 1 day of Sick leave left, so request that much. Request the rest
    as another type: Earned leave (6 days left)."."""
    have = max(left, ZERO)
    opening = (
        f"You have no {type_name} left."
        if have == ZERO
        else f"You have {_days(have)} of {type_name} left, so request that much."
    )
    usable = usable_others(others)
    names = ", ".join(
        o.name if o.left is None else f"{o.name} ({_days(o.left)} left)" for o in usable
    )
    rest = "the rest" if have > ZERO else "it"
    return f"{opening} Request {rest} as another type: {names}."


def refusal(
    leave_type: LeaveType,
    lop_days: Decimal,
    line: BalanceLine | None,
    lines: Sequence[BalanceLine],
) -> str | None:
    """Why the request is refused, or None if it may go ahead (or be part unpaid).

    Someone with no other leave left isn't refused: there's nothing to
    request instead, so the days past the balance are loss of pay.
    """
    if not leave_type.stops_at_balance or lop_days <= ZERO:
        return None
    if line is None or line.available is None:
        return None
    # Not a gender-limited type (period leave): it's for one purpose only.
    others = [
        Other(o.leave_type.name, o.available)
        for o in lines
        if o is not line and o.leave_type.eligible_genders is None
    ]
    if not usable_others(others):
        return None
    return over_balance_message(leave_type.name, line.available, others)
