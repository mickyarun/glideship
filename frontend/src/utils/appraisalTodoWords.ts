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

/** What each to-do item says, and how its due date reads (pure). */

import type { TodoItem } from '@/types/appraisalTodo'
import { longDate } from '@/utils/appraisalSetup'

/** Whole days from `today` to `day`, both ISO dates; negative when past. */
export function daysUntil(day: string, today: string): number {
  return Math.round((Date.parse(`${day}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000)
}

/** The item as a short instruction. `month` names the check-in's month when known. */
export function todoTitle(item: TodoItem, month = ''): string {
  const who = item.person_name ?? ''
  const n = item.count ?? 0
  switch (item.kind) {
    case 'check_in':
      return month ? `Write your ${month} check-in` : 'Write and send your check-in'
    case 'self_review':
      return 'Write your review'
    case 'read_result':
      return 'Read your result'
    case 'note':
      return `Write notes on ${who}'s check-in`
    case 'waiting_on_check_in':
      return `Waiting on ${who}'s check-in`
    case 'manager_review':
      return `Review ${who}'s quarter`
    case 'confirm_change':
      return n > 1 ? `Your manager suggested changes to ${n} goals` : 'Your manager suggested a change to a goal'
    case 'confirm_goals':
      return `Confirm ${n} goal${n === 1 ? '' : 's'} ${who} suggested`
    case 'set_goals':
      return `Add goals for ${who}`
    case 'open_reviews':
      return `Open reviews for ${item.cycle_name ?? 'the cycle'}`
    case 'fairness_check':
      return `Fairness check: ${n} review${n === 1 ? '' : 's'} in`
  }
}

/** The button on the item. */
export function todoAction(item: TodoItem): string {
  const words: Record<TodoItem['kind'], string> = {
    check_in: 'Start check-in',
    self_review: 'Start your review',
    read_result: 'Read it',
    note: 'Write notes',
    waiting_on_check_in: 'Open',
    manager_review: 'Start review',
    confirm_goals: 'Look at goals',
    confirm_change: 'Look at the change',
    set_goals: 'Add goals',
    open_reviews: 'Open the cycle',
    fairness_check: 'Open the fairness check',
  }
  return words[item.kind]
}

/** "Due Tue 8 Dec · 5 days left", "3 days late", or "" with no due date. */
export function dueLine(dueOn: string | null, today: string): string {
  if (!dueOn) return ''
  const days = daysUntil(dueOn, today)
  if (days < 0) {
    const late = -days
    return late >= 14 ? `${Math.floor(late / 7)} weeks late` : `${late} day${late === 1 ? '' : 's'} late`
  }
  if (days === 0) return `Due today, ${longDate(dueOn)}`
  return `Due ${longDate(dueOn)} · ${days} day${days === 1 ? '' : 's'} left`
}

/** Today as an ISO date in the viewer's own calendar. */
export function todayIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}
