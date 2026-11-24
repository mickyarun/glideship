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

/** Where each to-do item opens, and the counts on the nav and the tabs (pure). */

import type { RouteLocationRaw } from 'vue-router'
import type { TodoItem, TodoRole, TodoTarget } from '@/types/appraisalTodo'

const ROUTES: Record<TodoTarget, string> = {
  check_in: 'appraisal-check-in',
  review: 'appraisal-review',
  feedback: 'appraisal-feedback',
  goals: 'appraisal-goals',
  cycle: 'appraisal-cycle',
}

/** The page an item opens. */
export function todoRoute(item: TodoItem): RouteLocationRaw {
  return { name: ROUTES[item.target], params: { id: item.target_id } }
}

/** Something the caller can act on now; a note waiting on a check-in isn't yet. */
export function actionable(item: TodoItem): boolean {
  return item.kind !== 'waiting_on_check_in'
}

/** How many items the caller can act on sit on each tab. */
export function todoCounts(items: TodoItem[]): Record<TodoRole, number> {
  const counts: Record<TodoRole, number> = { own: 0, team: 0, cycles: 0 }
  for (const item of items.filter(actionable)) counts[item.role] += 1
  return counts
}
