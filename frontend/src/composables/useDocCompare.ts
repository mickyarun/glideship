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

// The Documents tab's version picker: picking an older version compares
// it with the current one (the current version itself just shows the
// document), closing goes back with focus on the version that was open,
// and a new document or card starts with no comparison and loads its
// history. Leaving an unsaved edit asks first (``leave``).

import { computed, nextTick, ref, watch, type Ref } from 'vue'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind } from '@/types/boards'

export function useDocCompare(kind: Ref<CardDocKind>, leave: () => Promise<boolean>) {
  const docs = useBoardCardDocsStore()
  const compareId = ref<string | null>(null)
  const history = computed(() => docs.history[kind.value])
  const comparing = computed(() => history.value?.items.find(v => v.id === compareId.value) ?? null)

  async function select(id: string): Promise<void> {
    const picked = history.value?.items.find(v => v.id === id)
    const next = !picked || picked.version === docs.current[kind.value]?.version ? null : id
    if (next !== compareId.value && (await leave())) compareId.value = next
  }

  async function closeCompare(): Promise<void> {
    const id = compareId.value
    compareId.value = null
    await nextTick()
    document.querySelector<HTMLElement>(`[data-version-id="${id}"]`)?.focus()
  }

  watch([kind, () => docs.card], ([k]) => {
    compareId.value = null
    if (!docs.history[k]?.loaded) void docs.loadVersions(k)
  }, { immediate: true })

  return { compareId, comparing, select, closeCompare }
}
