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

/** The end-of-period review: the caller's and team's lists, and the review on screen. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type { AppraisalSummary, GoalBody } from '@/types/appraisalGoals'
import type { AppraisalRead, ManagerBody, SelfBody } from '@/types/appraisalReview'
import { extractApiError } from '@/utils/errors'

const BASE = '/v1/appraisals'

export const useAppraisalReviewStore = defineStore('appraisalReview', () => {
  const mine = ref<AppraisalSummary[]>([])
  const team = ref<AppraisalSummary[]>([])
  const current = ref<AppraisalRead | null>(null)
  const error = ref('')
  const loading = ref(false)

  async function fetchLists(): Promise<void> {
    try {
      const [own, reports] = await Promise.all([
        api.get<AppraisalSummary[]>(`${BASE}/mine`),
        api.get<AppraisalSummary[]>(`${BASE}/team`),
      ])
      mine.value = own.data
      team.value = reports.data
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load your reviews. Reload to try again.")
    }
  }

  async function fetchOne(id: string): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      current.value = (await api.get<AppraisalRead>(`${BASE}/${id}`)).data
    } catch (err) {
      current.value = null
      error.value = extractApiError(err, "Couldn't load this review. Reload to try again.")
    } finally {
      loading.value = false
    }
  }

  async function act(send: () => Promise<{ data: AppraisalRead }>, fallback: string): Promise<string | null> {
    try {
      const data = (await send()).data
      if (current.value?.id === data.id) current.value = data
      return null
    } catch (err) {
      return extractApiError(err, fallback)
    }
  }

  const url = (id: string, path = '') => `${BASE}/${id}${path}`
  const saveSelf = (id: string, body: SelfBody) =>
    act(() => api.put<AppraisalRead>(url(id, '/self'), body), "Couldn't save your review.")
  const submitSelf = (id: string) =>
    act(() => api.post<AppraisalRead>(url(id, '/self/submit')), "Couldn't submit your review.")
  const saveManager = (id: string, body: ManagerBody) =>
    act(() => api.put<AppraisalRead>(url(id, '/manager'), body), "Couldn't save the review.")
  const submitManager = (id: string, body: ManagerBody) =>
    act(() => api.post<AppraisalRead>(url(id, '/manager/submit'), body), "Couldn't send the review to HR.")
  const sendBack = (id: string, note: string) =>
    act(() => api.post<AppraisalRead>(url(id, '/send-back'), { note }), "Couldn't send it back.")
  const share = (id: string) => act(() => api.post<AppraisalRead>(url(id, '/share')), "Couldn't share the result.")
  const acknowledge = (id: string, reply: string) =>
    act(() => api.post<AppraisalRead>(url(id, '/acknowledge'), { reply }), "Couldn't save your reply.")

  const saveGrowth = (id: string, strength: string, focus: string) =>
    act(() => api.put<AppraisalRead>(url(id, '/growth'), { strength, focus }), "Couldn't save the conversation.")
  const addNextGoal = (id: string, body: GoalBody) =>
    act(() => api.post<AppraisalRead>(url(id, '/next-goals'), body), "Couldn't add the goal.")
  const acceptNextGoal = (id: string, goalId: string) =>
    act(() => api.post<AppraisalRead>(url(id, `/next-goals/${goalId}/accept`)), "Couldn't confirm the goal.")
  const removeNextGoal = (id: string, goalId: string) =>
    act(() => api.delete<AppraisalRead>(url(id, `/next-goals/${goalId}`)), "Couldn't take the goal back.")

  return {
    saveGrowth, addNextGoal, acceptNextGoal, removeNextGoal,
    mine, team, current, error, loading, fetchLists, fetchOne,
    saveSelf, submitSelf, saveManager, submitManager, sendBack, share, acknowledge,
  }
})
