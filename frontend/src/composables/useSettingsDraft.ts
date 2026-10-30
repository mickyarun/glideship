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

// A settings form's draft of values the open board holds. The draft
// follows the board while it's untouched; once edited, a change from
// someone else marks a conflict instead of overwriting what I typed, so
// the page can offer to load theirs or save over it. Saving sends only the
// fields I changed, so someone else's other edits survive.

import { computed, ref, watch, type Ref } from 'vue'

function same<T>(a: T, b: T): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

function copy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function useSettingsDraft<T extends object>(source: () => T | null) {
  const base = ref(copy(source())) as Ref<T | null>
  const draft = ref(copy(source())) as Ref<T | null>
  const conflict = ref(false)

  const dirty = computed(() => !same(draft.value, base.value))

  /** Start over from what the board holds now. */
  function reset(): void {
    base.value = copy(source())
    draft.value = copy(source())
    conflict.value = false
  }

  watch(source, next => {
    if (same(next, base.value)) return
    if (dirty.value) conflict.value = true
    else reset()
  })
  // Undoing my edits during a conflict leaves nothing to keep.
  watch(dirty, isDirty => {
    if (!isDirty && conflict.value) reset()
  })

  /** The fields I changed since the draft started, with my values. */
  function changes(): Partial<T> {
    const start = base.value
    if (!draft.value || !start) return {}
    return Object.fromEntries(
      Object.entries(draft.value).filter(([k, v]) => !same(v, start[k as keyof T])),
    ) as Partial<T>
  }

  return { draft, dirty, conflict, reset, changes }
}
