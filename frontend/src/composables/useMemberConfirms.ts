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

// The member changes that ask first, and what they say: making the board
// members-only (everyone else loses it at once), and an admin lowering
// their own role (they lose these settings).

import { computed, ref } from 'vue'
import type { BoardPage } from '@/composables/useBoardPage'
import type { Grant, MemberSettings } from '@/composables/useMemberSettings'
import { useOrgName } from '@/composables/useOrgName'
import { ROLE_LABELS } from '@/constants/boards'
import { useAuthStore } from '@/stores/auth'
import type { BoardRole, BoardVisibility } from '@/types/boards'

export interface MemberAsk {
  title: string
  body: string
  action: string
  color: 'primary' | 'error'
  run: () => Promise<boolean>
}

export function useMemberConfirms(page: BoardPage, members: MemberSettings, visibility: () => BoardVisibility) {
  const asking = ref<MemberAsk | null>(null)
  const orgName = useOrgName()
  const auth = useAuthStore()
  const boardName = computed(() => page.board.detail.value?.board.name ?? 'this board')

  function pickVisibility(next: BoardVisibility): void {
    if (next !== 'members' || visibility() === 'members') {
      void members.setVisibility(next)
      return
    }
    asking.value = {
      title: `Make ${boardName.value} members only?`,
      body: `Everyone in ${orgName.value} without a role here loses access now, and it disappears from their search and switcher.`,
      action: 'Make members only',
      color: 'error',
      run: () => members.setVisibility(next),
    }
  }

  function pickRole(grant: Grant, role: BoardRole): void {
    const demotingMe = grant.kind === 'person' && grant.id === auth.user?.id && grant.role === 'admin' && role !== 'admin'
    if (!demotingMe) {
      void members.setRole(grant, role)
      return
    }
    asking.value = {
      title: `Make yourself ${role === 'editor' ? 'an' : 'a'} ${ROLE_LABELS[role]}?`,
      body: "You won't be able to change these settings.",
      action: `Make me ${ROLE_LABELS[role].toLowerCase()}`,
      color: 'error',
      run: () => members.setRole(grant, role),
    }
  }

  function confirmAsk(): void {
    const ask = asking.value
    asking.value = null
    void ask?.run()
  }

  return { asking, pickVisibility, pickRole, confirmAsk }
}
