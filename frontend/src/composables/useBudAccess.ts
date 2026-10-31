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

// Whether a handover's BUD can be opened (and its title shown) by me, as
// the server says on each handover (``can_open_bud``: ``buds:view`` with
// engineering access), and whether I may hand a card over at all.

import { usePermissions } from '@/composables/usePermissions'
import type { HandoverRead } from '@/types/boards'

export function useBudAccess() {
  const { hasPermission, canAccessEngineering } = usePermissions()

  function canOpen(h: Pick<HandoverRead, 'can_open_bud' | 'bud_id'>): boolean {
    return !!h.bud_id && h.can_open_bud
  }

  /** The BUD's title, only when I may open it. */
  function titleOf(h: Pick<HandoverRead, 'can_open_bud' | 'bud_id' | 'bud_title'>): string | null {
    return canOpen(h) ? h.bud_title ?? null : null
  }

  /**
   * What the server checks, besides my role on the board, before a
   * handover, its preview or a retry: engineering access with permission
   * to create and to view BUDs. The server re-checks; this only decides
   * whether to offer it.
   */
  function mayHandOver(): boolean {
    return canAccessEngineering.value && hasPermission('buds:create') && hasPermission('buds:view')
  }

  return { canOpen, titleOf, mayHandOver }
}
