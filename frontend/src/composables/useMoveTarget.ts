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

// The board a card is moving to, loaded when it's picked in the "Move to
// another board" dialog: its stages and labels, the people who can edit
// it and the repositories it links, for the preview and the stage locks.

import { ref } from 'vue'
import { boardsApi } from '@/services/boardsApi'
import type { MoveTarget } from '@/utils/boardMove'
import { logFailure } from '@/utils/logFailure'

export function useMoveTarget() {
  const target = ref<MoveTarget | null>(null)
  const loading = ref(false)
  const failed = ref(false)
  let seq = 0

  async function load(key: string | null): Promise<void> {
    const mine = ++seq
    target.value = null
    failed.value = false
    loading.value = !!key
    if (!key) return
    try {
      const [detail, people, repos] = await Promise.all([boardsApi.get(key), boardsApi.people(key), boardsApi.repos(key)])
      if (mine !== seq) return
      const { board, stages, labels } = detail
      target.value = { key: board.key, name: board.name, stages, labels, people: people.items, repos: repos.items }
    } catch (err) {
      if (mine === seq) failed.value = true
      logFailure('boards', 'move target fetch', err)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  return { target, loading, failed, load }
}
