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

// The handover dialog's preview: what a confirm would create (or link) for
// the chosen mode, landing stage and BUD. It's asked again whenever one of
// those changes; a reply to an earlier choice is dropped. The draft title
// and requirements start from it and stay as I edit them, until the
// choice changes; only edited values are sent as overrides.

import { computed, ref } from 'vue'
import { handoverApi } from '@/services/handoverApi'
import type { HandoverMode, HandoverOverrides, HandoverPreview, HandoverRequest } from '@/types/boards'
import type { HandoverTarget } from '@/types/boards/settings'
import { handoverFailure, type HandoverFailure } from '@/utils/handoverErrors'
import { logFailure } from '@/utils/logFailure'

export interface HandoverChoice {
  mode: HandoverMode
  target: HandoverTarget
  budId: string | null
}

export function useHandoverPreview(cardRef: () => { key: string; number: number } | null) {
  const preview = ref<HandoverPreview | null>(null)
  const loading = ref(false)
  const failure = ref<HandoverFailure | null>(null)
  const title = ref('')
  const requirements = ref('')
  const repoIds = ref<string[]>([])
  let seq = 0

  function request(choice: HandoverChoice): HandoverRequest | null {
    if (choice.mode === 'link') return choice.budId ? { mode: 'link', bud_id: choice.budId } : null
    return { mode: 'create', target_status: choice.target }
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
      if (mine !== seq) return
      preview.value = got
      title.value = got.title
      requirements.value = got.requirements_md
      repoIds.value = got.impacted_repos.map(r => r.repo_id)
    } catch (err) {
      if (mine !== seq) return
      preview.value = null
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
    const original = p.impacted_repos.map(r => r.repo_id)
    if (repoIds.value.length !== original.length || repoIds.value.some(id => !original.includes(id))) {
      out.impacted_repo_ids = [...repoIds.value]
    }
    return Object.keys(out).length ? out : undefined
  })

  function clear(): void {
    seq++
    preview.value = null
    failure.value = null
    loading.value = false
  }

  return { preview, loading, failure, title, requirements, repoIds, overrides, load, clear }
}

export type HandoverPreviewState = ReturnType<typeof useHandoverPreview>
