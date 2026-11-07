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
 * The appraisal intro guide: its facts from the API, and whether it is open.
 *
 * Opens by itself the first time someone visits an appraisal screen on
 * this browser; after that it is one click away. Remembering that is a
 * convenience only, so storage that fails just shows the guide again.
 */

import { ref } from 'vue'

import api from '@/services/api'
import type { GuideRead } from '@/types/appraisalSetup'
import { extractApiError } from '@/utils/errors'

const SEEN_KEY = 'appraisal-guide-seen'

const open = ref(false)
const guide = ref<GuideRead | null>(null)
const error = ref('')

function seen(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === '1'
  } catch {
    return false
  }
}

function remember(): void {
  try {
    localStorage.setItem(SEEN_KEY, '1')
  } catch {
    // Not remembered: the guide opens again next time, which is harmless.
  }
}

async function load(): Promise<void> {
  if (guide.value) return
  error.value = ''
  try {
    guide.value = (await api.get<GuideRead>('/v1/check-ins/guide')).data
  } catch (err) {
    error.value = extractApiError(err, "Couldn't load the guide. Close it and try again.")
  }
}

export function useAppraisalGuide() {
  async function show(): Promise<void> {
    open.value = true
    remember()
    await load()
  }

  /** On an appraisal screen's first visit: show the guide once. */
  async function showOnFirstVisit(): Promise<void> {
    if (!seen()) await show()
  }

  return { open, guide, error, show, showOnFirstVisit }
}
