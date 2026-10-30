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

// Unsaved drafts on a card's page (its description, a document): each
// editor reports what it holds unsaved, and anything that would drop it
// asks first: leaving the page or opening another card, switching tab,
// document or version, or importing a file over it.

import { computed, reactive } from 'vue'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'

export function useCardDrafts() {
  /** What each editor holds unsaved ("the description"), by editor. */
  const drafts = reactive<Record<string, string | null>>({})
  const what = computed(() => Object.values(drafts).find(Boolean) ?? null)
  const guard = useUnsavedGuard(computed(() => !!what.value), [], ['key', 'number'])

  /** An editor's report: what it holds unsaved, or null. */
  function report(editor: string, unsaved: string | null): void {
    drafts[editor] = unsaved
  }

  /** Resolves true when nothing is unsaved, or I agree to drop it. */
  async function confirmDiscard(): Promise<boolean> {
    return !what.value || guard.ask()
  }

  return { what, guard, report, confirmDiscard }
}
