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

// What follows an AI draft's review on the Documents tab. An edit of the
// draft is never thrown away by someone else's review: when the draft goes
// (accepted, rejected or replaced elsewhere) while I'm part way through
// editing it, my text moves into the document's editor, with a note saying
// what became of the draft and who did it; the note goes once that edit is
// saved or cancelled, or another document opens. A draft I accepted offers
// Undo, which makes the version before it current again (as a new version).

import { ref, watch, type Ref } from 'vue'
import { DOC_NAMES } from '@/constants/boards'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind, CardDocState, DocRead } from '@/types/boards'

/** What became of a draft, by the state its change announced. */
const OUTCOMES: Record<CardDocState, string> = {
  current: 'accepted',
  rejected: 'rejected',
  superseded: 'replaced',
  pending_review: 'replaced by a newer draft',
}
const NEXT_STEP = 'Save it as a new version, or cancel to drop it.'

export interface KeptEdit {
  kind: CardDocKind
  text: string
  note: string
}

/** A draft I accepted as ``version``, on top of ``previous`` (null when it was the first). */
export interface AcceptedDraft {
  kind: CardDocKind
  version: number
  previous: number | null
}

export function useDraftKeep(kind: Ref<CardDocKind>, nameFor: (id: string) => string) {
  const docs = useBoardCardDocsStore()
  /** My unsaved edit of the draft shown, if any. */
  const editText = ref<string | null>(null)
  const kept = ref<KeptEdit | null>(null)
  const accepted = ref<AcceptedDraft | null>(null)
  const undoing = ref(false)

  function noteFor(k: CardDocKind): string {
    const change = docs.changes[k]
    if (!change) return `Your edit is kept — the draft is no longer waiting for review. ${NEXT_STEP}`
    const by = change.actor ? ` by ${nameFor(change.actor)}` : ''
    return `Your edit is kept — the draft was ${OUTCOMES[change.state]}${by}. ${NEXT_STEP}`
  }

  // Runs before the draft's view goes, so the edit is still in hand.
  watch(() => docs.drafts[kind.value], (next: DocRead | undefined, before: DocRead | undefined) => {
    if (next || !before || before.kind !== kind.value || editText.value === null) return
    kept.value = { kind: kind.value, text: editText.value, note: noteFor(kind.value) }
    editText.value = null
  })
  watch(kind, () => {
    kept.value = null
    editText.value = null
  })

  /** The editor's edit was saved or cancelled: the note has done its job. */
  function settled(): void {
    kept.value = null
  }

  /** Make the version before the accepted draft current again; resolves the error, if any, and the words for success. */
  async function undo(): Promise<{ error: string | null; success: string }> {
    const held = accepted.value
    if (!held || held.previous === null) return { error: null, success: '' }
    undoing.value = true
    const error = await docs.restore(held.kind, held.previous)
    undoing.value = false
    if (!error) accepted.value = null
    return { error, success: `Put the ${DOC_NAMES[held.kind]} back to version ${held.previous}` }
  }

  return { editText, kept, accepted, undoing, settled, undo }
}
