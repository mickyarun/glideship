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

/** HR's role templates, including each one's trends. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type { RoleTemplate, RoleTemplateBody, Trend } from '@/types/roleTemplate'
import { extractApiError } from '@/utils/errors'

const BASE = '/v1/appraisals/role-templates'

export const useRoleTemplatesStore = defineStore('roleTemplates', () => {
  const templates = ref<RoleTemplate[]>([])
  const error = ref('')
  const loading = ref(false)

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      templates.value = (await api.get<RoleTemplate[]>(BASE)).data
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load the role templates.")
    } finally {
      loading.value = false
    }
  }

  function put(saved: RoleTemplate): void {
    const at = templates.value.findIndex(t => t.id === saved.id)
    if (at >= 0) templates.value.splice(at, 1, saved)
    else templates.value.push(saved)
  }

  async function write(send: () => Promise<{ data: RoleTemplate }>, fallback: string): Promise<string | null> {
    try {
      put((await send()).data)
      return null
    } catch (err) {
      return extractApiError(err, fallback)
    }
  }

  const create = (body: RoleTemplateBody) =>
    write(() => api.post<RoleTemplate>(BASE, body), "Couldn't create the template.")
  const update = (id: string, body: RoleTemplateBody) =>
    write(() => api.put<RoleTemplate>(`${BASE}/${id}`, body), "Couldn't save the template.")
  const saveTrends = (id: string, trends: Trend[]) =>
    write(() => api.put<RoleTemplate>(`${BASE}/${id}/trends`, trends), "Couldn't save the trends.")
  const approveTrends = (id: string) =>
    write(() => api.post<RoleTemplate>(`${BASE}/${id}/trends/approve`), "Couldn't approve the trends.")

  /** Start an AI draft; the job id, or an error message. */
  async function draftTrends(id: string): Promise<{ jobId?: string; error?: string }> {
    try {
      return { jobId: (await api.post<{ jobId: string }>(`${BASE}/${id}/trends/draft`)).data.jobId }
    } catch (err) {
      return { error: extractApiError(err, "Couldn't start the draft.") }
    }
  }

  async function remove(id: string): Promise<string | null> {
    try {
      await api.delete(`${BASE}/${id}`)
      templates.value = templates.value.filter(t => t.id !== id)
      return null
    } catch (err) {
      return extractApiError(err, "Couldn't delete the template.")
    }
  }

  return { templates, error, loading, fetchAll, create, update, saveTrends, approveTrends, draftTrends, remove }
})
