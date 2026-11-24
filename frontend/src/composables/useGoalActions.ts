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

/**
 * Acting on one person's goals: the dialogs (add, edit, reword, decline),
 * the buttons on each goal, picking a starting point, and asking for AI
 * ideas, with polling while they are written. Shared by the set-goals and
 * confirm-goals pages.
 */

import { onBeforeUnmount, ref, watch } from 'vue'

import { useAppraisalGoalsStore } from '@/stores/appraisalGoals'
import type { Goal, GoalBody, GoalOption } from '@/types/appraisalGoals'
import type { GoalDialogMode } from '@/utils/appraisalGoals'

const POLL_MS = 10_000

export function useGoalActions() {
  const store = useAppraisalGoalsStore()
  const message = ref('')
  const dialog = ref<GoalDialogMode | null>(null)
  const start = ref<Partial<GoalBody>>({})
  const target = ref<Goal | null>(null)
  const busy = ref(false)
  const dialogError = ref('')
  const suggestNote = ref('')

  function open(mode: GoalDialogMode, goal: Goal | null = null, words: Partial<GoalBody> = {}): void {
    target.value = goal
    start.value = words
    dialogError.value = ''
    dialog.value = mode
  }

  async function run(action: Promise<string | null>): Promise<void> {
    message.value = (await action) ?? ''
  }

  const manager = () => Boolean(store.current?.can_add)
  const cardEvents = {
    accept: (goal: Goal) => run(store.accept(goal.id)),
    remove: (goal: Goal) => run(store.remove(goal.id)),
    reword: (goal: Goal) => open('reword', goal),
    dismiss: (goal: Goal) =>
      goal.status === 'proposed' && manager() ? open('decline', goal) : run(store.dismiss(goal.id, '')),
    // A manager always says why; the person rewords their own proposal freely.
    edit: (goal: Goal) => open(manager() ? 'edit-reason' : 'edit', goal, { title: goal.title, measure: goal.measure }),
    'suggest-change': (goal: Goal) => open('suggest-change', goal, { title: goal.title, measure: goal.measure }),
  }

  function pick(option: GoalOption): void {
    open(manager() ? 'add' : 'propose', null, {
      title: option.title,
      measure: [option.measure, option.measure_source].filter(Boolean).join(' · '),
      source: option.source === 'role_library' ? 'role_library' : null,
    })
  }

  async function submitDialog(body: GoalBody): Promise<void> {
    const goal = target.value
    const mode = dialog.value
    busy.value = true
    let problem: string | null = null
    if (mode === 'propose' || mode === 'add') problem = await store.add(body)
    else if (goal && (mode === 'edit' || mode === 'edit-reason')) problem = await store.edit(goal.id, body)
    else if (goal && mode === 'suggest-change') problem = await store.suggestChange(goal.id, body)
    else if (goal && mode === 'reword') problem = await store.askReword(goal.id, body.reason)
    else if (goal && mode === 'decline') problem = await store.dismiss(goal.id, body.reason)
    busy.value = false
    dialogError.value = problem ?? ''
    if (!problem) dialog.value = null
  }

  // While AI ideas are being written, look for them now and then.
  let poll: ReturnType<typeof setInterval> | undefined
  watch(
    () => store.current?.suggest_status,
    (status, before) => {
      clearInterval(poll)
      if (status === 'pending') poll = setInterval(() => void store.refresh(), POLL_MS)
      if (before === 'pending' && (status === 'failed' || status === 'none')) {
        suggestNote.value = 'No ideas came back this time. Pick from the library or write your own.'
      }
    },
    { immediate: true },
  )
  onBeforeUnmount(() => clearInterval(poll))

  function suggest(): Promise<void> {
    suggestNote.value = ''
    return run(store.suggest())
  }

  return { store, message, dialog, start, busy, dialogError, suggestNote, open, run, cardEvents, pick, submitDialog, suggest }
}
