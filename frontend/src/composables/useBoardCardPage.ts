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

// Everything a card's page runs: the card (useBoardCard) with its edits,
// checklist, history, comment thread and documents, and what the page
// says back after each action: a live-region announcement on success,
// the snackbar on failure, and "Archived OPS-3" with Undo. A card reached
// by a key it had before a move says so once ("SEO-14 is now OPS-3").

import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { useBoardCard } from '@/composables/useBoardCard'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useCardActivity } from '@/composables/useCardActivity'
import { useCardChecklist } from '@/composables/useCardChecklist'
import { useCardEdits } from '@/composables/useCardEdits'
import { useCardPageActions, type FieldGuide } from '@/composables/useCardPageActions'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { takeMoveNote } from '@/composables/useMovedCard'
import { cardUrl } from '@/services/boardsApi'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import { useBoardsStore } from '@/stores/boards'
import { createCommentThread } from '@/stores/commentThread'
import type { CardDetail } from '@/types/boards'
import { CARD_COMMENT_WIRE } from '@/utils/boardCardWire'

export function useBoardCardPage(number: Ref<number | null>, guide: FieldGuide) {
  const feedback = useBoardFeedback()
  const docs = useBoardCardDocsStore()
  const boardsStore = useBoardsStore()
  const directory = useMemberDirectory()
  const attachments = ref<{ reload: () => void } | null>(null)

  const card = useBoardCard(number, {
    onUpdated: () => void checklist.load(),
    onActivity: () => {
      void thread.value?.fetch()
      attachments.value?.reload()
      activity.refresh()
    },
    onDoc: kind => {
      void docs.refresh(kind)
      // A PRD saved elsewhere: the card has one now (card_updated follows
      // with the rest), so stages that need one let it in.
      if (kind !== 'prd' || !detail.value) return
      detail.value = { ...detail.value, has_prd: true }
      void edits.refresh()
    },
    onHistory: () => activity.refresh(),
  })
  const { page, detail, boardKey } = card
  const edits = useCardEdits(card)
  const cardRef = computed(() => (detail.value ? { key: boardKey.value, number: detail.value.number } : null))
  const checklist = useCardChecklist(cardRef, edits.setChecklistCount)
  const activity = useCardActivity(cardRef)

  // One path per card, so edits to the card don't remake its thread.
  const path = computed(() => (cardRef.value ? cardUrl(cardRef.value.key, cardRef.value.number) : null))
  const threadError = ref<string | null>(null)
  const thread = computed(() =>
    path.value ? createCommentThread(path.value, threadError, () => activity.refresh(), CARD_COMMENT_WIRE) : null,
  )
  watch(threadError, error => feedback.fail(error))

  watch(path, () => {
    if (!cardRef.value) return
    void checklist.load()
    activity.reset()
    void docs.open(cardRef.value)
  }, { immediate: true })

  const can = page.board.can
  /** Archived cards (and boards) are read-only until restored. */
  const open = computed(() => !detail.value?.archived_at && !page.board.archived.value)
  const canEdit = computed(() => open.value && can('edit_card'))
  const canMove = computed(() => open.value && can('move_card'))
  const canComment = computed(() => open.value && can('comment'))
  const canArchive = computed(() => !page.board.archived.value && can('archive_card'))
  const stages = computed(() => page.board.detail.value?.stages ?? [])
  const stage = computed(() => stages.value.find(s => s.id === detail.value?.stage_id) ?? null)
  const limits = computed(() => boardsStore.limits)

  const nameFor = (id: string) => page.people.find(id)?.name ?? directory.nameFor(id)
  const photoFor = (id: string) => {
    const person = page.people.find(id)
    return person ? person.avatar_url : directory.photoFor(id)
  }

  const actions = useCardPageActions({ card, edits, checklist, activity, feedback, stages, guide })

  const movedNote = ref<string | null>(null)
  watch(() => detail.value?.key, key => (movedNote.value = key ? takeMoveNote(key) : null), { immediate: true })
  /** Moved to another board from here: its page there, with the note. */
  async function movedBoard(moved: CardDetail, boardName: string): Promise<void> {
    const from = detail.value?.key ?? moved.key
    feedback.announce(`${from} moved to ${boardName} as ${moved.key}`)
    await card.goTo(moved, from)
  }

  onMounted(() => {
    void directory.ensureLoaded()
    void boardsStore.ensureLimits()
  })
  // The documents belong to this page; nothing of them outlives it.
  onUnmounted(() => docs.reset())

  return {
    card, page, detail, boardKey, feedback, checklist, activity, thread, attachments, docs,
    canEdit, canMove, canComment, canArchive, stages, stage, limits, nameFor, photoFor, actions, movedNote, movedBoard,
  }
}
