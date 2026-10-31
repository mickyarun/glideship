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

// What the board page says back after I act: a live-region announcement
// ("Moved SEO-36 to Review", "Link copied"), focus returned to a card I
// moved from its menu, and the snackbar (errors, and "Archived SEO-36"
// with Undo).

import { nextTick, ref } from 'vue'

export interface Toast {
  text: string
  /** An Undo-style action on the snackbar. */
  action?: { label: string; run: () => void }
  error?: boolean
  /** Stays until dismissed or acted on (a refusal whose action I may want). */
  persist?: boolean
}

export function useBoardFeedback() {
  const announcement = ref('')
  const toast = ref<Toast | null>(null)
  const toastOpen = ref(false)

  function announce(text: string): void {
    // Clearing first makes a repeat of the same words be read again.
    announcement.value = ''
    void nextTick(() => {
      announcement.value = text
    })
  }

  function show(next: Toast): void {
    toast.value = next
    toastOpen.value = true
  }

  function fail(error: string | null): boolean {
    if (error) show({ text: error, error: true })
    return !!error
  }

  /** Focus a card's title link once it has rendered where it landed. */
  async function focusCard(cardId: string): Promise<boolean> {
    await nextTick()
    const link = document.querySelector<HTMLElement>(`[data-card-id="${cardId}"] .card-tile__link`)
    link?.focus()
    return !!link
  }

  /** Focus a stage column's heading, when the card itself isn't in view. */
  function focusStage(stageId: string): void {
    const heading = document.querySelector<HTMLElement>(`[data-stage-col="${stageId}"] h2`)
    if (heading) {
      heading.tabIndex = -1
      heading.focus()
    }
  }

  return { announcement, toast, toastOpen, announce, show, fail, focusCard, focusStage }
}
