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

/** The manager's team page: the queue's order, each person's standing, first visit (pure). */

import type { TeamRow } from '@/types/appraisalTeam'
import type { TodoItem } from '@/types/appraisalTodo'
import { actionable } from '@/utils/appraisalTodo'

/** The team's to-do, oldest due first; undated work (like goals) after; waiting last. */
export function teamQueue(items: TodoItem[]): TodoItem[] {
  const team = items.filter(i => i.role === 'team')
  const key = (i: TodoItem) => [actionable(i) ? 0 : 1, i.due_on ?? '9999-12-31'] as const
  return [...team].sort((a, b) => {
    const [ka, kb] = [key(a), key(b)]
    return ka[0] - kb[0] || ka[1].localeCompare(kb[1])
  })
}

export type Standing = 'Waiting on you' | 'Needs goals' | 'Up to date'

/** One person's line in the "Everyone" table, from what is on the manager's to-do. */
export function standing(row: TeamRow, items: TodoItem[]): Standing {
  const theirs = items.filter(i => i.role === 'team' && i.person_name === row.person_name && actionable(i))
  if (theirs.some(i => i.kind === 'set_goals')) return 'Needs goals'
  return theirs.length ? 'Waiting on you' : 'Up to date'
}

/** A manager's first visit: nobody has goals yet and no check-in has opened. */
export function isFirstRun(rows: TeamRow[]): boolean {
  return rows.length > 0 && rows.every(r => r.goals_accepted === 0 && r.months.every(m => m.state === 'not_open'))
}

/** "MC" for "Maya Chen". */
export function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase() ?? '').join('')
}
