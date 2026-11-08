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

/** Wording for goals: where they came from, their history, and results (pure). */

import type { Goal, GoalHistory, GoalResult, SuggestionBasis } from '@/types/appraisalGoals'

/** Which goal form the dialog shows. */
export type GoalDialogMode = 'propose' | 'add' | 'edit' | 'edit-reason' | 'suggest-change' | 'reword' | 'decline'

export const BASIS_LABELS: Record<SuggestionBasis, string> = {
  feedback: 'From your feedback',
  last_period: 'From last period',
  blocker: "From what's blocking you",
  trend: 'Market trend',
  role_library: 'Role library',
}

export const RESULT_OPTIONS: { label: string; value: GoalResult }[] = [
  { label: 'Achieved', value: 'achieved' },
  { label: 'Partly', value: 'partly' },
  { label: 'Not yet', value: 'not_yet' },
]

export function resultLabel(result: GoalResult | null): string {
  return RESULT_OPTIONS.find(r => r.value === result)?.label ?? 'Not scored'
}

function shortDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

/** Who a goal is from, as the employee should read it. */
export function originLine(goal: Goal): string {
  if (goal.origin === 'ai_suggested') return 'AI-suggested'
  if (goal.origin === 'manager_added') return `Added by ${goal.proposed_by_name || 'your manager'}`
  if (goal.origin === 'role_library') return `From the role library, picked by ${goal.proposed_by_name || 'them'}`
  return `${goal.proposed_by_name || 'Their'} own goal`
}

/** One history line: "Changed by Ravi on 8 Dec, from “…”: reason". */
export function historyLine(entry: GoalHistory): string {
  const who = `${entry.by_name || 'Someone'} on ${shortDay(entry.at)}`
  const why = entry.reason ? `: ${entry.reason}` : ''
  switch (entry.kind) {
    case 'created':
      return `Added by ${who}${why}`
    case 'edited':
      return `Changed by ${who}${entry.before ? `, from “${entry.before.title}”` : ''}${why}`
    case 'confirmed':
      return `Confirmed by ${who}`
    case 'reword_asked':
      return `${who} asked for a rewording${why}`
    case 'declined':
      return `Not added by ${who}${why}`
    default:
      return `Removed by ${who}${why}`
  }
}

/** Goals in the sections the page shows them in. */
export function goalSections(goals: Goal[]): Record<'accepted' | 'waiting' | 'suggested' | 'dismissed', Goal[]> {
  return {
    accepted: goals.filter(g => g.status === 'accepted'),
    waiting: goals.filter(g => g.status === 'proposed'),
    suggested: goals.filter(g => g.status === 'suggested'),
    dismissed: goals.filter(g => g.status === 'dismissed'),
  }
}
