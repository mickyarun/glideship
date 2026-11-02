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

import { ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useBudAgentOptions } from '@/composables/useBudAgentOptions'
import { useBUDStore } from '@/stores/bud'
import type { BUDPriority } from '@/types'

/**
 * State and submit logic for the New BUD form. The stage agents and their
 * skills come from useBudAgentOptions, shared with the handover dialog.
 */
export function useBudCreateForm(open: Ref<boolean>) {
  const router = useRouter()
  const budStore = useBUDStore()
  const agents = useBudAgentOptions(open)

  const title = ref('')
  const description = ref('')
  const priority = ref<BUDPriority>('P2')
  const creating = ref(false)
  const error = ref('')
  /** Which expansion panels are open; empty means Advanced is closed. */
  const openPanels = ref<string[]>([])

  function reset(): void {
    title.value = ''
    description.value = ''
    priority.value = 'P2'
    agents.reset()
    openPanels.value = []
  }

  async function submit(): Promise<void> {
    if (!title.value.trim() || creating.value) return
    creating.value = true
    error.value = ''
    const { phases, overrides } = agents.choices()
    const bud = await budStore.createBUD(
      title.value.trim(),
      description.value.trim() || undefined,
      overrides,
      phases,
      priority.value,
    )
    creating.value = false
    if (!bud) {
      error.value = budStore.error || "Couldn't create the BUD. Try again."
      return
    }
    open.value = false
    reset()
    void router.push(`/buds/${bud.id}`)
  }

  return {
    title,
    description,
    priority,
    creating,
    error,
    openPanels,
    agents,
    submit,
  }
}
