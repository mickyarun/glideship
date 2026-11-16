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

/** Manager feedback: the team list and the item being written. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type { FeedbackBody, FeedbackRead, FeedbackRow } from '@/types/appraisalFeedback'
import { extractApiError } from '@/utils/errors'

const BASE = '/v1/manager-feedback'

export const useManagerFeedbackStore = defineStore('managerFeedback', () => {
  const team = ref<FeedbackRow[]>([])
  const current = ref<FeedbackRead | null>(null)
  const teamError = ref('')
  const error = ref('')
  const loading = ref(false)

  async function fetchTeam(): Promise<void> {
    teamError.value = ''
    try {
      team.value = (await api.get<FeedbackRow[]>(`${BASE}/team`)).data
    } catch (err) {
      teamError.value = extractApiError(err, "Couldn't load your team's feedback. Reload to try again.")
    }
  }

  async function fetchOne(id: string): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      current.value = (await api.get<FeedbackRead>(`${BASE}/${id}`)).data
    } catch (err) {
      current.value = null
      error.value = extractApiError(err, "Couldn't load this feedback. Reload to try again.")
    } finally {
      loading.value = false
    }
  }

  async function write(send: () => Promise<{ data: FeedbackRead }>, fallback: string): Promise<string | null> {
    try {
      const data = (await send()).data
      if (current.value?.id === data.id) current.value = data
      return null
    } catch (err) {
      return extractApiError(err, fallback)
    }
  }

  const save = (id: string, body: FeedbackBody) =>
    write(() => api.put<FeedbackRead>(`${BASE}/${id}`, body), "Couldn't save the feedback. Try again.")
  const markDone = (id: string) =>
    write(() => api.post<FeedbackRead>(`${BASE}/${id}/done`), "Couldn't mark it done. Try again.")

  return { team, current, teamError, error, loading, fetchTeam, fetchOne, save, markDone }
})
