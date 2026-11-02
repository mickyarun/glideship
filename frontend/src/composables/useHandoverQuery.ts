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

// ``?handover=1`` on a card's page (the board's card menu sends it): once
// the card's handovers have loaded, open the dialog if I may hand it over,
// or say why not. The query is removed either way, so a reload or Back
// doesn't ask again.

import { watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import { HANDOVER_QUERY_KEY } from '@/constants/boards'

interface Options {
  /** The board hands cards over (or the card already holds handovers). */
  shown: () => boolean
  loaded: Ref<boolean>
  allowed: () => boolean
  cardKey: () => string
  open: () => void
  feedback: () => ReturnType<typeof useBoardFeedback>
}

export function useHandoverQuery(o: Options) {
  const route = useRoute()
  const router = useRouter()

  function drop(): void {
    const query = { ...route.query }
    delete query[HANDOVER_QUERY_KEY]
    void router.replace({ query })
  }

  function refuse(text: string): void {
    o.feedback().show({ text, persist: true })
    o.feedback().announce(text)
  }

  watch([() => route.query[HANDOVER_QUERY_KEY], o.shown, o.loaded], ([asked, shown, loaded]) => {
    if (!asked) return
    if (!shown) {
      drop()
      refuse("This board doesn't hand cards over to Delivery.")
      return
    }
    if (!loaded) return
    drop()
    if (o.allowed()) o.open()
    else refuse(`You can't hand ${o.cardKey()} over. It needs edit access on this board, engineering access and permission to create BUDs.`)
  }, { immediate: true })
}
