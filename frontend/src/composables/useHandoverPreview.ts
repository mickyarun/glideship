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

// The handover dialog's draft: the preview for the chosen mode and landing,
// and my edits to its title, requirements, repositories and priority. A
// new choice asks for a new preview; what I've edited stays (it differs
// from the preview it started from) and only untouched fields take the new
// preview's values. A preview that fails keeps the last good one in view,
// with the failure beside the choice that caused it, so I can pick again.

import { computed, ref } from 'vue'
import { handoverApi } from '@/services/handoverApi'
import type { BUDPriority } from '@/types'
import type { HandoverMode, HandoverOverrides, HandoverPreview, HandoverRequest } from '@/types/boards'
import type { HandoverTarget } from '@/types/boards/settings'
import { handoverFailure, type HandoverFailure } from '@/utils/handoverErrors'
import { logFailure } from '@/utils/logFailure'

export interface HandoverChoice {
  mode: HandoverMode
  target: HandoverTarget
  budId: string | null
}

const repoIdsOf = (p: HandoverPreview) => p.impacted_repos.map(r => r.repo_id)
const sameIds = (a: string[], b: string[]) => a.length === b.length && a.every(id => b.includes(id))

export function useHandoverPreview(cardRef: () => { key: string; number: number } | null) {
  const preview = ref<HandoverPreview | null>(null)
  const loading = ref(false)
  const failure = ref<HandoverFailure | null>(null)
  const title = ref('')
  const requirements = ref('')
  const repoIds = ref<string[]>([])
  const priority = ref<BUDPriority>('P2')
  let seq = 0

  function request(choice: HandoverChoice): HandoverRequest | null {
    if (choice.mode === 'link') return choice.budId ? { mode: 'link', bud_id: choice.budId } : null
    return { mode: 'create', target_status: choice.target }
  }

  /** Take the new preview's values where I haven't changed the last one's. */
  function adopt(next: HandoverPreview): void {
    const was = preview.value
    if (!was || title.value === was.title) title.value = next.title
    if (!was || requirements.value === was.requirements_md) requirements.value = next.requirements_md
    if (!was || sameIds(repoIds.value, repoIdsOf(was))) repoIds.value = repoIdsOf(next)
    if (!was || priority.value === was.priority) priority.value = next.priority
    preview.value = next
  }

  /** Ask for the preview of this choice; a link with no BUD picked has none. */
  async function load(choice: HandoverChoice): Promise<void> {
    const card = cardRef()
    const body = request(choice)
    const mine = ++seq
    failure.value = null
    if (!card || !body) {
      preview.value = null
      loading.value = false
      return
    }
    loading.value = true
    try {
      const got = await handoverApi.preview(card.key, card.number, body)
      if (mine === seq) adopt(got)
    } catch (err) {
      if (mine !== seq) return
      failure.value = handoverFailure(err, "Couldn't prepare the handover. Try again.")
      logFailure('boards', 'handover preview', err)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  /** The draft's edits, against the preview; undefined when nothing changed. */
  const overrides = computed<HandoverOverrides | undefined>(() => {
    const p = preview.value
    if (!p || p.mode === 'link') return undefined
    const out: HandoverOverrides = {}
    if (title.value.trim() && title.value.trim() !== p.title) out.title = title.value.trim()
    if (requirements.value !== p.requirements_md) out.requirements_md = requirements.value
    if (!sameIds(repoIds.value, repoIdsOf(p))) out.impacted_repo_ids = [...repoIds.value]
    return Object.keys(out).length ? out : undefined
  })

  /** The priority I picked, when it isn't the preview's (the card's, else P2). */
  const priorityChange = computed<BUDPriority | undefined>(() => {
    const p = preview.value
    return p && p.mode === 'create' && priority.value !== p.priority ? priority.value : undefined
  })

  /** Forget the draft: the next preview fills every field afresh. */
  function clear(): void {
    seq++
    preview.value = null
    failure.value = null
    loading.value = false
  }

  return { preview, loading, failure, title, requirements, repoIds, priority, overrides, priorityChange, load, clear }
}

export type HandoverPreviewState = ReturnType<typeof useHandoverPreview>
