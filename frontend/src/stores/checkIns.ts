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
  // Lists and the open check-in keep their own state, so one screen's
  // error never shows on another.
  const loading = ref(false)
  const error = ref('')
  const listLoading = ref(false)
  const listError = ref('')
  // Guards against a slow response for an earlier check-in landing last.
  let request = 0

  async function fetchList(path: string, fallback: string): Promise<CheckInSummary[]> {
    listLoading.value = true
    listError.value = ''
    try {
      return (await api.get<CheckInSummary[]>(`${BASE}/${path}`)).data
    } catch (err) {
      listError.value = extractApiError(err, fallback)
      return []
    } finally {
      listLoading.value = false
    }
  }

  async function fetchMine(): Promise<void> {
    mine.value = await fetchList('mine', "Couldn't load your check-ins. Reload to try again.")
  }

  async function fetchTeam(): Promise<void> {
    team.value = await fetchList('team', "Couldn't load your team's check-ins. Reload to try again.")
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
      const data = (await send()).data
      // A slow save for one check-in mustn't replace another now on screen.
      if (current.value?.id === data.id) current.value = data
      return null
    } catch (err) {
      return extractApiError(err, fallback)
    }
  }

  /** Pick up a finished draft without touching anything else on screen. */
  async function refreshDraft(id: string): Promise<void> {
    const data = (await api.get<CheckInRead>(`${BASE}/${id}`)).data
    if (current.value?.id !== id) return
    const { ai_lines, ai_hidden, can_regenerate, draft_status } = data
    current.value = { ...current.value, ai_lines, ai_hidden, can_regenerate, draft_status }
  }

  function regenerate(id: string): Promise<string | null> {
    return write(() => api.post(`${BASE}/${id}/regenerate`), "Couldn't ask for a new draft. Try again.")
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
    mine, team, current, loading, error, listLoading, listError,
    fetchMine, fetchTeam, fetchOne, refreshDraft, regenerate, saveNote, saveTag, addLink, removeLink, saveGoalValue,
  }
})
