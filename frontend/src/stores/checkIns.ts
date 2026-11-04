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
 * Monthly check-ins: the caller's own, one open check-in at a time, and
 * their reports' latest. Write actions return `null` or a user-facing
 * error; every write answers with the whole check-in, which replaces the
 * one on screen.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type {
  CheckInNote,
  CheckInRead,
  CheckInSummary,
  FactTag,
  GoalValueIn,
  LinkCreate,
} from '@/types/appraisal'
import { extractApiError } from '@/utils/errors'

const BASE = '/v1/check-ins'

export const useCheckInsStore = defineStore('checkIns', () => {
  const mine = ref<CheckInSummary[]>([])
  const team = ref<CheckInSummary[]>([])
  const current = ref<CheckInRead | null>(null)
  const loading = ref(false)
  const error = ref('')
  // Guards against a slow response for an earlier check-in landing last.
  let request = 0

  async function fetchMine(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      mine.value = (await api.get<CheckInSummary[]>(`${BASE}/mine`)).data
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load your check-ins. Reload to try again.")
    } finally {
      loading.value = false
    }
  }

  async function fetchTeam(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      team.value = (await api.get<CheckInSummary[]>(`${BASE}/team`)).data
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load your team's check-ins. Reload to try again.")
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id: string): Promise<void> {
    const mineRequest = ++request
    loading.value = true
    error.value = ''
    try {
      const data = (await api.get<CheckInRead>(`${BASE}/${id}`)).data
      if (mineRequest === request) current.value = data
    } catch (err) {
      if (mineRequest === request) {
        current.value = null
        error.value = extractApiError(err, "Couldn't load this check-in. Reload to try again.")
      }
    } finally {
      if (mineRequest === request) loading.value = false
    }
  }

  async function write(send: () => Promise<{ data: CheckInRead }>, fallback: string): Promise<string | null> {
    try {
      current.value = (await send()).data
      return null
    } catch (err) {
      return extractApiError(err, fallback)
    }
  }

  function saveNote(id: string, note: CheckInNote): Promise<string | null> {
    return write(() => api.put(`${BASE}/${id}/note`, note), "Couldn't save. Try again.")
  }

  function saveTag(id: string, itemId: string, tag: FactTag | null): Promise<string | null> {
    return write(
      () => api.put(`${BASE}/${id}/fact-tags`, { [itemId]: tag }),
      "Couldn't save which goal it helped. Try again.",
    )
  }

  function addLink(id: string, body: LinkCreate): Promise<string | null> {
    return write(() => api.post(`${BASE}/${id}/links`, body), "Couldn't add the link. Try again.")
  }

  async function removeLink(id: string, linkId: string): Promise<string | null> {
    try {
      await api.delete(`${BASE}/${id}/links/${linkId}`)
      await fetchOne(id)
      return null
    } catch (err) {
      return extractApiError(err, "Couldn't remove the link. Try again.")
    }
  }

  function saveGoalValue(id: string, goalId: string, body: GoalValueIn): Promise<string | null> {
    return write(
      () => api.put(`${BASE}/${id}/goal-values/${goalId}`, body),
      "Couldn't save the value. Try again.",
    )
  }

  return {
    mine, team, current, loading, error,
    fetchMine, fetchTeam, fetchOne, saveNote, saveTag, addLink, removeLink, saveGoalValue,
  }
})
