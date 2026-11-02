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

// The card page's open tab and, on the Documents tab, which document.
// Switching either closes its editors, so an unsaved draft asks first
// (``confirmDiscard``); a refused switch stays where it was.

import { computed, ref } from 'vue'
import { DOC_KINDS } from '@/constants/boards'
import type { CardDocKind } from '@/types/boards'

const FIRST_CARD_TAB = 'overview'

export function useCardTabs(confirmDiscard: () => Promise<boolean>) {
  const openTab = ref(FIRST_CARD_TAB)
  const docKind = ref<CardDocKind>(DOC_KINDS[0])

  /** Open a tab (and document); resolves false when an unsaved draft kept it here. */
  async function goTo(next: string, kind: CardDocKind = docKind.value): Promise<boolean> {
    if (next === openTab.value && kind === docKind.value) return true
    if (!(await confirmDiscard())) return false
    openTab.value = next
    docKind.value = kind
    return true
  }

  const tab = computed({ get: () => openTab.value, set: next => void goTo(next) })

  return { tab, docKind, goTo }
}
