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

/** One person's goals for a period, their options, and every goal action. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type { GoalBody, GoalOption, GoalsRead } from '@/types/appraisalGoals'
import { extractApiError } from '@/utils/errors'

const BASE = '/v1/appraisals'

export const useAppraisalGoalsStore = defineStore('appraisalGoals', () => {
  const current = ref<GoalsRead | null>(null)
  const options = ref<GoalOption[]>([])
  const error = ref('')
  const loading = ref(false)

  async function fetch(appraisalId: string): Promise<void> {
    loading.value = true
    error.value = ''
    options.value = []
    try {
      current.value = (await api.get<GoalsRead>(`${BASE}/${appraisalId}/goals`)).data
    } catch (err) {
      current.value = null
      error.value = extractApiError(err, "Couldn't load the goals. Reload to try again.")
    } finally {
      loading.value = false
    }
    // Starting points are a help, not the page: without them the goals still show.
    try {
      options.value = (await api.get<GoalOption[]>(`${BASE}/${appraisalId}/goal-options`)).data
    } catch {
      options.value = []
    }
  }

  /** Run one action; the error message, or null when it worked. */
  async function act(send: () => Promise<{ data: GoalsRead }>, fallback: string): Promise<string | null> {
    try {
      current.value = (await send()).data
      return null
    } catch (err) {
      return extractApiError(err, fallback)
    }
  }

  const id = () => current.value?.appraisal_id ?? ''
  const add = (body: GoalBody) =>
    act(() => api.post<GoalsRead>(`${BASE}/${id()}/goals`, body), "Couldn't add the goal.")
  const edit = (goalId: string, body: GoalBody) =>
    act(() => api.patch<GoalsRead>(`${BASE}/goals/${goalId}`, body), "Couldn't change the goal.")
  const remove = (goalId: string) =>
    act(() => api.delete<GoalsRead>(`${BASE}/goals/${goalId}`), "Couldn't remove the goal.")
  const accept = (goalId: string) =>
    act(() => api.post<GoalsRead>(`${BASE}/goals/${goalId}/accept`), "Couldn't confirm the goal.")
  const dismiss = (goalId: string, reason: string) =>
    act(() => api.post<GoalsRead>(`${BASE}/goals/${goalId}/dismiss`, { reason }), "Couldn't dismiss the goal.")
  const askReword = (goalId: string, reason: string) =>
    act(() => api.post<GoalsRead>(`${BASE}/goals/${goalId}/ask-reword`, { reason }), "Couldn't send it back.")
  const suggestChange = (goalId: string, body: GoalBody) =>
    act(
      () => api.post<GoalsRead>(`${BASE}/goals/${goalId}/suggest-change`, body),
      "Couldn't suggest the change.",
    )
  const suggest = () =>
    act(() => api.post<GoalsRead>(`${BASE}/${id()}/suggest-goals`), "Couldn't ask for suggestions.")

  /** Look again without the spinner, while suggestions are being written. */
  async function refresh(): Promise<void> {
    if (!current.value) return
    try {
      current.value = (await api.get<GoalsRead>(`${BASE}/${id()}/goals`)).data
    } catch {
      // The next look tries again.
    }
  }

  return {
    current, options, error, loading, fetch, refresh,
    add, edit, remove, accept, dismiss, askReword, suggestChange, suggest,
  }
})
