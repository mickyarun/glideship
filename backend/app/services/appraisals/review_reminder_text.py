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

"""The words of the review-step reminders (pure): counts, dates and links only."""

from datetime import date

from app.services.appraisals.reminder_text import TEAM_PATH, link, short_date
from app.services.appraisals.reminders import Moment

MY_REVIEW_PATH = "/appraisals/review"


def self_text(moment: Moment, cycle: str, due: date, base_url: str) -> str:
    """The employee's self-review reminder."""
    when = short_date(due)
    lines = {
        Moment.OPENS: f"Your {cycle} review is open. Score your goals and the period by {when}.",
        Moment.BEFORE: f"Your {cycle} self-review is due {when}.",
        Moment.DUE: f"Your {cycle} self-review is due today.",
        Moment.AFTER: f"Your {cycle} self-review was due {when}.",
    }
    return f"{lines[moment]} {link(base_url, MY_REVIEW_PATH, 'Open your review')}"


def review_text(
    moment: Moment, cycle: str, due: date, waiting: int, total: int, base_url: str
) -> str:
    """The manager's reminder for their team's reviews."""
    when, done = short_date(due), total - waiting
    lines = {
        Moment.OPENS: f"{cycle}: {waiting} {'review is' if waiting == 1 else 'reviews are'} "
        f"ready for you. Due {when}.",
        Moment.BEFORE: f"{cycle} reviews due {when}: {done} of {total} done.",
        Moment.DUE: f"{cycle} reviews are due today: {done} of {total} done.",
        Moment.AFTER: f"{cycle} reviews were due {when}: {done} of {total} done.",
    }
    return f"{lines[moment]} {link(base_url, TEAM_PATH, 'Open team')}"


def result_text(moment: Moment, cycle: str, due: date, base_url: str) -> str:
    """The employee's reminder to read and acknowledge their result."""
    when = short_date(due)
    lines = {
        Moment.OPENS: f"Your {cycle} result is ready. Read it and reply by {when}.",
        Moment.BEFORE: f"Please read your {cycle} result by {when}.",
        Moment.DUE: f"Please read your {cycle} result today.",
        Moment.AFTER: f"Your {cycle} result is waiting for you; it was due {when}.",
    }
    return f"{lines[moment]} {link(base_url, MY_REVIEW_PATH, 'Open your result')}"
