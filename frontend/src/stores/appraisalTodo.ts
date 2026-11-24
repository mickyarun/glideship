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

/** The caller's appraisal to-do list: the home list and the nav badge. */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import api from '@/services/api'
import type { TodoItem } from '@/types/appraisalTodo'
import { actionable, todoCounts } from '@/utils/appraisalTodo'
import { extractApiError } from '@/utils/errors'

export const useAppraisalTodoStore = defineStore('appraisalTodo', () => {
  const items = ref<TodoItem[]>([])
  const counts = computed(() => todoCounts(items.value))
  /** What the nav badge counts: everything the caller can act on now. */
  const total = computed(() => items.value.filter(actionable).length)
  const late = computed(() => items.value.filter(i => i.late).length)

  /** Why the list couldn't load, for pages built on it; the badge just stays empty. */
  const error = ref('')

  async function fetch(): Promise<void> {
    try {
      items.value = (await api.get<TodoItem[]>('/v1/appraisals/todo')).data
      error.value = ''
    } catch (err) {
      items.value = []
      error.value = extractApiError(err, "Couldn't load what's waiting on you. Reload to try again.")
    }
  }

  return { items, counts, total, late, error, fetch }
})
