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

"""The rules tying review periods, check-ins and feedback together (pure).

The same rules are check constraints on ``appraisal_cycles``; checking
them here first turns a bad choice into a message instead of a 500.
"""

from datetime import date

from app.models.appraisal_enums import CheckInCadence, FeedbackCadence, ReviewPeriod

PERIOD_MONTHS: dict[ReviewPeriod, int] = {
    ReviewPeriod.QUARTERLY: 3,
    ReviewPeriod.HALF_YEARLY: 6,
    ReviewPeriod.YEARLY: 12,
}
CADENCE_MONTHS: dict[CheckInCadence, int] = {
    CheckInCadence.MONTHLY: 1,
    CheckInCadence.QUARTERLY: 3,
}


def cadence_error(
    review: ReviewPeriod, checkins: CheckInCadence, feedback: FeedbackCadence
) -> str | None:
    """Why this combination can't run, or None when it can."""
    if checkins is CheckInCadence.QUARTERLY and review is ReviewPeriod.QUARTERLY:
        return "Quarterly check-ins need half-yearly or yearly reviews."
    if feedback is FeedbackCadence.IN_REVIEW:
        if review is not ReviewPeriod.QUARTERLY:
            return "Feedback in the review only fits quarterly reviews."
        return None
    if feedback is FeedbackCadence.MONTHLY and checkins is not CheckInCadence.MONTHLY:
        return "Monthly feedback needs monthly check-ins."
    if feedback is FeedbackCadence.QUARTERLY and review is ReviewPeriod.QUARTERLY:
        return "With quarterly reviews, pick monthly feedback or feedback in the review."
    return None


def add_months(day: date, months: int) -> date:
    """The first of the month ``months`` after ``day``'s month."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def slices(start: date, end: date, months: int) -> list[tuple[date, date]]:
    """Consecutive [first, last] date ranges of ``months`` months covering a period.

    ``start`` must be the first of a month; the last slice stops at ``end``.
    """
    out: list[tuple[date, date]] = []
    first = start
    while first <= end:
        nxt = add_months(first, months)
        out.append((first, min(end, date.fromordinal(nxt.toordinal() - 1))))
        first = nxt
    return out


def period_after(
    previous_end: date | None, today: date, review: ReviewPeriod
) -> tuple[date, date]:
    """The next review period: after the last cycle, else the one holding ``today``.

    Periods line up with calendar quarters, halves or years.
    """
    months = PERIOD_MONTHS[review]
    if previous_end is not None:
        start = date.fromordinal(previous_end.toordinal() + 1)
    else:
        aligned = (today.month - 1) // months * months + 1
        start = date(today.year, aligned, 1)
    end = date.fromordinal(add_months(start, months).toordinal() - 1)
    return start, end
