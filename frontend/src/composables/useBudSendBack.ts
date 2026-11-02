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

// Whether the open BUD can go back to the card it came from: the card
// still holds it, it hasn't reached development, and I may edit BUDs.
// The header's menu offers it; BUDSendBack asks for the reason.

import { computed } from 'vue'
import { usePermissions } from '@/composables/usePermissions'
import { useBudOriginStore } from '@/stores/budOrigin'
import type { BUDDocument } from '@/types'
import { canSendBack } from '@/utils/handoverChips'

export function useBudSendBack(bud: () => BUDDocument | null) {
  const store = useBudOriginStore()
  const { hasPermission } = usePermissions()

  /** The card it came from, once this BUD's origin has loaded. */
  const card = computed(() => {
    const b = bud()
    return b && store.budId === b.id ? store.origin?.card ?? null : null
  })
  const offered = computed(() => {
    const b = bud()
    return !!b && !!card.value && !!store.active && canSendBack(b.status) && hasPermission('buds:edit')
  })

  function ask(): void {
    store.askSendBack()
  }

  return { card, offered, ask }
}
