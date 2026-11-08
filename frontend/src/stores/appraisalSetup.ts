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

/** HR's appraisal setup: org settings, cycles, readiness and progress. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type {
  AppraisalSettings,
  CycleCreate,
  CycleProgress,
  CycleRead,
  CycleUpdate,
  EnrolmentReport,
  Readiness,
} from '@/types/appraisalSetup'
import type { Calibration } from '@/types/appraisalReview'
import { extractApiError } from '@/utils/errors'

const BASE = '/v1/appraisals'

export const useAppraisalSetupStore = defineStore('appraisalSetup', () => {
  const settings = ref<AppraisalSettings | null>(null)
  const cycles = ref<CycleRead[]>([])
  const cycle = ref<CycleRead | null>(null)
  const readiness = ref<Readiness | null>(null)
  const progress = ref<CycleProgress | null>(null)
  const calibration = ref<Calibration | null>(null)
  const error = ref('')
  const loading = ref(false)

  async function load<T>(path: string, fallback: string): Promise<T | null> {
    loading.value = true
    error.value = ''
    try {
      return (await api.get<T>(`${BASE}/${path}`)).data
    } catch (err) {
      error.value = extractApiError(err, fallback)
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchSettings(): Promise<void> {
    settings.value = await load<AppraisalSettings>('settings', "Couldn't load the appraisal settings.")
  }

  async function fetchCycles(): Promise<void> {
    cycles.value = (await load<CycleRead[]>('cycles', "Couldn't load the cycles.")) ?? []
  }

  /** The cycle, with readiness while it's a draft and progress once it runs. */
  async function fetchCycle(id: string): Promise<void> {
    cycle.value = await load<CycleRead>(`cycles/${id}`, "Couldn't load this cycle.")
    readiness.value = null
    progress.value = null
    if (!cycle.value) return
    if (cycle.value.status === 'draft') {
      readiness.value = await load<Readiness>(`cycles/${id}/readiness`, "Couldn't check readiness.")
    } else {
      progress.value = await load<CycleProgress>(`cycles/${id}/progress`, "Couldn't load progress.")
    }
  }

  /** Run a write; the error message, or null when it worked. */
  async function attempt<T>(send: () => Promise<{ data: T }>, fallback: string): Promise<[T | null, string | null]> {
    try {
      return [(await send()).data, null]
    } catch (err) {
      return [null, extractApiError(err, fallback)]
    }
  }

  async function saveSettings(body: AppraisalSettings): Promise<string | null> {
    const [data, problem] = await attempt(
      () => api.put<AppraisalSettings>(`${BASE}/settings`, body),
      "Couldn't save the settings.",
    )
    if (data) settings.value = data
    return problem
  }

  async function createCycle(body: CycleCreate): Promise<[CycleRead | null, string | null]> {
    return attempt(() => api.post<CycleRead>(`${BASE}/cycles`, body), "Couldn't create the cycle.")
  }

  async function updateCycle(id: string, body: CycleUpdate): Promise<string | null> {
    const [data, problem] = await attempt(
      () => api.patch<CycleRead>(`${BASE}/cycles/${id}`, body),
      "Couldn't save the cycle.",
    )
    if (data) await fetchCycle(data.id)
    return problem
  }

  async function deleteCycle(id: string): Promise<string | null> {
    const [, problem] = await attempt(() => api.delete(`${BASE}/cycles/${id}`), "Couldn't delete the cycle.")
    return problem
  }

  async function activate(id: string): Promise<[EnrolmentReport | null, string | null]> {
    const result = await attempt(
      () => api.post<EnrolmentReport>(`${BASE}/cycles/${id}/activate`),
      "Couldn't open the cycle.",
    )
    if (result[0]) await fetchCycle(id)
    return result
  }

  async function close(id: string): Promise<string | null> {
    const [data, problem] = await attempt(
      () => api.post<CycleRead>(`${BASE}/cycles/${id}/close`),
      "Couldn't close the cycle.",
    )
    if (data) await fetchCycle(id)
    return problem
  }

  /** A cycle action with a count back; the message to show. */
  async function count(id: string, path: string, ok: (n: number) => string, fallback: string): Promise<string> {
    const [data, problem] = await attempt(() => api.post<Record<string, number>>(`${BASE}/cycles/${id}/${path}`), fallback)
    if (data) await fetchCycle(id)
    return problem ?? ok(Object.values(data ?? {})[0] ?? 0)
  }

  const startReview = (id: string) =>
    count(id, 'start-review', n => `Review opened for ${n} people.`, "Couldn't open the review.")
  const shareAll = (id: string) =>
    count(id, 'share', n => `Shared ${n} results.`, "Couldn't share the results.")
  const suggestAll = (id: string) =>
    count(id, 'suggest-goals', n => `Asked for suggested goals for ${n} people.`, "Couldn't ask for suggestions.")

  return {
    calibration,
    startReview,
    shareAll,
    suggestAll,
    settings,
    cycles,
    cycle,
    readiness,
    progress,
    error,
    loading,
    fetchSettings,
    fetchCycles,
    fetchCycle,
    saveSettings,
    createCycle,
    updateCycle,
    deleteCycle,
    activate,
    close,
  }
})
