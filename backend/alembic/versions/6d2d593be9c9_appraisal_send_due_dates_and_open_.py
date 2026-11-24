"""appraisal send, due dates and open answers

Check-ins and manager notes become private to their writer until sent,
and both get due dates: a check-in five working days after its period
ends, a manager note five working days after the check-in it answers is
sent (a cycle's ``feedback_due_days`` now counts from that send). The
self-review gains two open answers, check-ins get due-date reminders
(a new ``digest_claim_kind`` value), and a cycle records when HR last
reminded everyone late by hand.

Existing data carries forward. Everything people could read before this
migration stays readable: every existing check-in with something in it
the manager could read, and every manager note with something written in
it, is marked sent at its last update. Blank check-ins stay unsent.
Existing check-ins get a due date five weekdays after their period (the
person's holidays aren't known here); one still open gets at least five
weekdays from the day this runs, so people can keep writing it. Existing
notes keep their due date, except: one written but not finished also
gets five weekdays from today, so the manager can finish and send it;
and one answering a blank, still-open check-in loses its date and waits
for that check-in, like any new note. Cycles not yet closed and stored
org settings take the decided five days for notes (closed cycles keep
theirs; the downgrade puts back the old default of ten, not any earlier
custom value). Orgs get ``min_goals`` of three, or their ``max_goals``
when that is lower.
Autogenerate doesn't compare check constraints, so that swap is spelled
out.

Revision ID: 6d2d593be9c9
Revises: 52934796567f
Create Date: 2026-11-24 13:54:49.624024

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6d2d593be9c9"
down_revision: str | None = "52934796567f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DUE_DAYS = 5
CHECK_IN_DUE_KIND = "appraisal_check_in_due"
OLD_FEEDBACK_DUE_DAYS = 10

# The fifth weekday after each existing check-in's period ends.


def weekdays_after(day: str) -> str:
    """SQL for the fifth weekday after the date expression ``day``."""
    return (
        f"(SELECT d::date FROM generate_series({day} + 1, {day} + 14, interval '1 day') d"
        f" WHERE extract(isodow FROM d) < 6 ORDER BY d OFFSET {DUE_DAYS - 1} LIMIT 1)"
    )


# Usually five weekdays after the period. One still open gets at least a
# fresh window from today, so nobody is locked out of a check-in they are
# still writing: a sent check-in can change only until its due date.
CHECK_IN_DUE = f"""
UPDATE appraisal_check_ins c SET due_on = CASE
    WHEN c.closed_at IS NULL
        THEN GREATEST({weekdays_after("c.period_end")}, {weekdays_after("CURRENT_DATE")})
    ELSE {weekdays_after("c.period_end")}
END
WHERE due_on IS NULL
"""

# A note written but not finished counts as sent (the person could read it)
# and keeps a window from today, so the manager can still finish and send it.
UNFINISHED_NOTES_DUE = f"""
UPDATE appraisal_manager_feedback SET due_on = GREATEST(due_on, {weekdays_after("CURRENT_DATE")})
WHERE sent_at IS NOT NULL AND status = 'open'
"""

SETTINGS = f"""
UPDATE organizations SET config = jsonb_set(
    config,
    '{{appraisals}}',
    (config -> 'appraisals') || jsonb_build_object(
        'min_goals', LEAST(3, COALESCE((config -> 'appraisals' ->> 'max_goals')::int, 3)),
        'checkin_due_days', {DUE_DAYS},
        'feedback_due_days', {DUE_DAYS}
    )
)
WHERE jsonb_typeof(config -> 'appraisals') = 'object'
"""

# A blank check-in stays unsent and open, so the note answering it has
# nothing to answer yet: it loses its old due date and waits, dated once the
# check-in is sent or closes. Notes on closed check-ins keep theirs, or they
# would be dated from an old close and late at once.
NOTES_WAITING_ON_CHECK_IN = """
UPDATE appraisal_manager_feedback f SET due_on = NULL
WHERE f.sent_at IS NULL AND EXISTS (
    SELECT 1 FROM appraisal_check_ins c
    WHERE c.org_id = f.org_id AND c.cycle_id = f.cycle_id AND c.profile_id = f.profile_id
      AND c.period_end = f.period_end AND c.sent_at IS NULL AND c.closed_at IS NULL
)
"""

# Run after the schema changes; a test runs the same statements.
# A check-in counts as sent only if the person wrote or attached something
# in it: lines, links, tags or goal values. An AI draft alone doesn't count
# (AI cycles draft every check-in unasked). A blank one stays unsent, so the
# person gets the normal Send step.
CHECK_INS_WITH_CONTENT = """
UPDATE appraisal_check_ins c SET sent_at = c.updated_at
WHERE c.sent_at IS NULL AND (
    c.employee_note IS NOT NULL
    OR c.fact_tags <> '{}'::jsonb
    OR EXISTS (SELECT 1 FROM appraisal_evidence_links l WHERE l.check_in_id = c.id)
    OR EXISTS (SELECT 1 FROM appraisal_goal_values v WHERE v.check_in_id = c.id)
)
"""

# Rolling back drops "sent", after which every check-in and note is readable
# by its manager or person again. Clear unsent drafts first so a downgrade
# never shows anyone what its writer hadn't sent.
CLEAR_UNSENT = (
    "UPDATE appraisal_manager_feedback SET keep_note = NULL, try_note = NULL,"
    " goal_notes = NULL, goal_status = '{}'::jsonb WHERE sent_at IS NULL",
    "DELETE FROM appraisal_evidence_links WHERE check_in_id IN"
    " (SELECT id FROM appraisal_check_ins WHERE sent_at IS NULL)",
    "DELETE FROM appraisal_goal_values WHERE check_in_id IN"
    " (SELECT id FROM appraisal_check_ins WHERE sent_at IS NULL)",
    "UPDATE appraisal_check_ins SET employee_note = NULL, ai_summary = NULL,"
    " fact_tags = '{}'::jsonb,"
    # Written in but cleared: open while open, missed once closed, as if empty.
    " status = CASE WHEN status = 'employee_added' THEN"
    " (CASE WHEN closed_at IS NULL THEN 'open' ELSE 'missed' END)::appraisal_check_in_status"
    " ELSE status END"
    " WHERE sent_at IS NULL",
)

BACKFILL = (
    CHECK_INS_WITH_CONTENT,
    CHECK_IN_DUE,
    "UPDATE appraisal_manager_feedback SET sent_at = updated_at"
    " WHERE sent_at IS NULL AND (keep_note IS NOT NULL OR try_note IS NOT NULL"
    " OR goal_status <> '{}'::jsonb)",
    UNFINISHED_NOTES_DUE,
    NOTES_WAITING_ON_CHECK_IN,
    f"UPDATE appraisal_cycles SET feedback_due_days = {DUE_DAYS} WHERE status <> 'closed'",
    SETTINGS,
)


def upgrade() -> None:
    # The check-in due-date reminders' claim kind. A new enum value can't be
    # used in the transaction that adds it on pg14, so it commits on its own.
    with op.get_context().autocommit_block():
        op.execute(f"ALTER TYPE digest_claim_kind ADD VALUE IF NOT EXISTS '{CHECK_IN_DUE_KIND}'")
    op.add_column("appraisal_check_ins", sa.Column("due_on", sa.Date(), nullable=True))
    op.add_column(
        "appraisal_check_ins", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "appraisal_check_ins",
        sa.Column("edited_after_send_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_appraisal_check_ins_unsent",
        "appraisal_check_ins",
        ["org_id", "due_on"],
        unique=False,
        postgresql_where="sent_at IS NULL",
    )
    op.add_column(
        "appraisal_cycles",
        sa.Column("checkin_due_days", sa.SmallInteger(), server_default="5", nullable=False),
    )
    op.add_column(
        "appraisal_cycles",
        sa.Column("hr_reminded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint("ck_appraisal_cycles_offsets", "appraisal_cycles", type_="check")
    op.create_check_constraint(
        "ck_appraisal_cycles_offsets",
        "appraisal_cycles",
        "feedback_due_days >= 0 AND checkin_due_days >= 1 AND hr_overdue_offset >= 0",
    )
    op.add_column(
        "appraisal_manager_feedback",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "appraisal_manager_feedback",
        sa.Column("edited_after_send_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("appraisal_manager_feedback", "due_on", existing_type=sa.DATE(), nullable=True)
    op.create_index(
        "ix_appraisal_feedback_unsent",
        "appraisal_manager_feedback",
        ["org_id", "manager_user_id"],
        unique=False,
        postgresql_where="sent_at IS NULL",
    )
    op.add_column("appraisals", sa.Column("self_proud", sa.LargeBinary(), nullable=True))
    op.add_column("appraisals", sa.Column("self_differently", sa.LargeBinary(), nullable=True))

    # Existing data: nothing readable yesterday disappears today.
    for statement in BACKFILL:
        op.execute(statement)


def downgrade() -> None:
    for statement in CLEAR_UNSENT:
        op.execute(statement)
    # Postgres can't drop an enum value; its claims go, the unused value stays.
    op.execute(f"DELETE FROM digest_claims WHERE kind = '{CHECK_IN_DUE_KIND}'")
    op.execute(
        "UPDATE organizations SET config = jsonb_set(config, '{appraisals}',"
        " (config -> 'appraisals') - 'min_goals' - 'checkin_due_days'"
        f" || jsonb_build_object('feedback_due_days', {OLD_FEEDBACK_DUE_DAYS}))"
        " WHERE jsonb_typeof(config -> 'appraisals') = 'object'"
    )
    op.execute(
        f"UPDATE appraisal_cycles SET feedback_due_days = {OLD_FEEDBACK_DUE_DAYS}"
        " WHERE status <> 'closed'"
    )
    # Notes waiting on an unsent check-in have no due date; give them the old one.
    op.execute(
        "UPDATE appraisal_manager_feedback"
        f" SET due_on = period_end + {OLD_FEEDBACK_DUE_DAYS} WHERE due_on IS NULL"
    )
    op.drop_column("appraisals", "self_differently")
    op.drop_column("appraisals", "self_proud")
    op.drop_index(
        "ix_appraisal_feedback_unsent",
        table_name="appraisal_manager_feedback",
        postgresql_where="sent_at IS NULL",
    )
    op.alter_column(
        "appraisal_manager_feedback", "due_on", existing_type=sa.DATE(), nullable=False
    )
    op.drop_column("appraisal_manager_feedback", "edited_after_send_at")
    op.drop_column("appraisal_manager_feedback", "sent_at")
    op.drop_constraint("ck_appraisal_cycles_offsets", "appraisal_cycles", type_="check")
    op.create_check_constraint(
        "ck_appraisal_cycles_offsets",
        "appraisal_cycles",
        "feedback_due_days >= 0 AND hr_overdue_offset >= 0",
    )
    op.drop_column("appraisal_cycles", "checkin_due_days")
    op.drop_column("appraisal_cycles", "hr_reminded_at")
    op.drop_index(
        "ix_appraisal_check_ins_unsent",
        table_name="appraisal_check_ins",
        postgresql_where="sent_at IS NULL",
    )
    op.drop_column("appraisal_check_ins", "edited_after_send_at")
    op.drop_column("appraisal_check_ins", "sent_at")
    op.drop_column("appraisal_check_ins", "due_on")
