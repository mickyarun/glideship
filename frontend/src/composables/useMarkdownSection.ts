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

import { ref } from 'vue'

/**
 * Edit one markdown text in place: the editing/editValue/toggle/save
 * pattern behind the BUD's requirements and tech spec tabs, a card's
 * description and its documents. ``current`` reads the saved text (null
 * when there's nothing to save to yet); ``save`` writes a changed value
 * and may resolve ``false`` to keep the editor open, e.g. after a failed
 * save, so the draft isn't lost.
 */
export function useMarkdownSection(
  current: () => string | null,
  save: (value: string) => Promise<boolean | void>,
) {
  const editing = ref(false)
  const editValue = ref('')

  function toggle(): void {
    if (editing.value) {
      void commit()
    } else {
      editValue.value = current() ?? ''
      editing.value = true
    }
  }

  async function commit(): Promise<void> {
    const saved = current()
    if (saved === null) return
    if (editValue.value !== saved && (await save(editValue.value)) === false) return
    editing.value = false
  }

  return { editing, editValue, toggle, save: commit }
}
