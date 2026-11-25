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
 * The appraisal guide: its facts from the API, and whether it is open.
 *
 * It opens only when someone asks for it ("How appraisals work"); it never
 * opens by itself. The facts also carry HR's note to everyone, which the
 * home page shows. They are kept per signed-in person, so switching account
 * or org never shows someone else's.
 */

import { ref } from 'vue'

import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { GuideRead } from '@/types/appraisalSetup'
import { extractApiError } from '@/utils/errors'

const open = ref(false)
const guide = ref<GuideRead | null>(null)
const error = ref('')
// Who the loaded facts belong to.
let loadedFor = ''

export function useAppraisalGuide() {
  const auth = useAuthStore()

  /** Load the facts for the signed-in person, once; whether they loaded. */
  async function load(): Promise<boolean> {
    const who = `${auth.user?.id ?? ''}:${auth.user?.org_id ?? ''}`
    if (guide.value && loadedFor === who) return true
    guide.value = null
    error.value = ''
    try {
      guide.value = (await api.get<GuideRead>('/v1/check-ins/guide')).data
      loadedFor = who
      return true
    } catch (err) {
      error.value = extractApiError(err, "Couldn't load the guide. Close it and try again.")
      return false
    }
  }

  async function show(): Promise<void> {
    open.value = true
    await load()
  }

  return { open, guide, error, show, load }
}
