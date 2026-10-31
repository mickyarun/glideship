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

// Accepting (as is, or edited) and rejecting an AI draft of a card
// document. Accepting sends the current version the reviewer compared
// against; if someone saved a newer one meanwhile, the server refuses
// (409), the documents reload so the comparison uses it, and the reviewer
// accepts again. A draft someone else reviewed (or a newer draft replaced)
// is a 404 whose words say so. Either way the drafts are read again
// (``settle``) once the outcome is reported.

import { ref } from 'vue'
import { DOC_NAMES } from '@/constants/boards'
import { boardCardApi } from '@/services/boardCardApi'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { DocRead } from '@/types/boards'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

export interface ReviewResult {
  error: string | null
  /** Someone saved a newer version while I reviewed. */
  conflict: boolean
}

export function useDraftReview() {
  const docs = useBoardCardDocsStore()
  const busy = ref<'accept' | 'reject' | null>(null)

  /** Make the draft (or ``body``, my edit of it) the current version on top of ``base``. */
  async function accept(draft: DocRead, base: number | null, body?: string): Promise<ReviewResult> {
    busy.value = 'accept'
    const result = await docs.write(
      draft.kind,
      c => boardCardApi.acceptDraft(c.key, c.number, draft.kind, draft.id, base, body),
      `Couldn't accept the ${DOC_NAMES[draft.kind]} draft. Try again.`,
    )
    busy.value = null
    if (result.conflict) {
      return { error: `Someone saved a newer ${DOC_NAMES[draft.kind]} while you reviewed. The changes now compare with it; check them and accept again.`, conflict: true }
    }
    return result
  }

  async function reject(draft: DocRead): Promise<string | null> {
    const c = docs.card
    if (!c) return null
    busy.value = 'reject'
    try {
      await boardCardApi.rejectDraft(c.key, c.number, draft.kind, draft.id)
      return null
    } catch (err) {
      logFailure('boards', 'draft reject', err)
      return extractApiError(err, `Couldn't reject the ${DOC_NAMES[draft.kind]} draft. Try again.`)
    } finally {
      busy.value = null
    }
  }

  /** Read the drafts again once the outcome is reported (the draft's view goes away with it). */
  function settle(): Promise<void> {
    return docs.loadDocs()
  }

  return { busy, accept, reject, settle }
}
