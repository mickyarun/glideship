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

// A card page opened with ``?focus=<field>`` (the board's "Open card" after
// a refused move) shows that field's tab and focuses the field once the
// card has drawn, then drops the query so a reload doesn't do it again.
// ``show`` does the same for a refusal on the page itself.

import { nextTick, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { StageRequiredField } from '@/types/boards'
import { FOCUS_QUERY_KEY, focusField, focusFrom, tabFor } from '@/utils/cardFocus'

export function useCardFieldFocus(ready: Ref<boolean>, openTab: (tab: string) => void) {
  const route = useRoute()
  const router = useRouter()

  async function show(field: StageRequiredField): Promise<void> {
    openTab(tabFor(field))
    // The tab draws, then its panels (the documents load their editor).
    await nextTick()
    await nextTick()
    if (!focusField(field)) setTimeout(() => focusField(field), 0)
  }

  watch(
    [ready, () => route.query[FOCUS_QUERY_KEY]],
    ([isReady, value]) => {
      const field = focusFrom(value)
      if (!isReady || !field) return
      const query = { ...route.query }
      delete query[FOCUS_QUERY_KEY]
      void router.replace({ query })
      void show(field)
    },
    { immediate: true },
  )

  return { show }
}
