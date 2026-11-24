// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/** A draft cycle's setup form: its editable settings (pure). */

import type { CycleRead, CycleUpdate } from '@/types/appraisalSetup'


/** A cycle's editable settings, copied for a form. */
export function cycleForm(c: CycleRead): Required<CycleUpdate> {
  return {
    name: c.name,
    self_due: c.self_due,
    manager_due: c.manager_due,
    ack_due: c.ack_due,
    checkin_cadence: c.checkin_cadence,
    feedback_cadence: c.feedback_cadence,
    feedback_due_days: c.feedback_due_days,
    reminder_offsets: [...c.reminder_offsets],
    overdue_nudge: c.overdue_nudge,
    hr_overdue_list: c.hr_overdue_list,
    hr_overdue_offset: c.hr_overdue_offset,
    ai_drafting: c.ai_drafting,
    suggest_goals_on_open: c.suggest_goals_on_open,
    intro_note: c.intro_note,
  }
}
