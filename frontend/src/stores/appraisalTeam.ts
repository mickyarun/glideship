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

/** The manager's team at a glance: each report's goals, months and notes. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '@/services/api'
import type { TeamRow } from '@/types/appraisalTeam'
import { extractApiError } from '@/utils/errors'

export const useAppraisalTeamStore = defineStore('appraisalTeam', () => {
  const rows = ref<TeamRow[]>([])
  const loaded = ref(false)
  const error = ref('')

  async function fetch(): Promise<void> {
    error.value = ''
    try {
      rows.value = (await api.get<TeamRow[]>('/v1/appraisals/team-overview')).data
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load your team. Reload to try again.")
    } finally {
      loaded.value = true
    }
  }

  return { rows, loaded, error, fetch }
})
