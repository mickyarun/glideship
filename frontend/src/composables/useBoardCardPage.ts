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
// the snackbar on failure, and "Archived OPS-3" with Undo.

import { computed, onMounted, ref, watch, type Ref } from 'vue'
import { useBoardCard } from '@/composables/useBoardCard'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useCardActivity } from '@/composables/useCardActivity'
import { useCardChecklist } from '@/composables/useCardChecklist'
import { useCardEdits } from '@/composables/useCardEdits'
import { useMemberDirectory } from '@/composables/useMemberDirectory'
import { cardUrl } from '@/services/boardsApi'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import { useBoardsStore } from '@/stores/boards'
import { createCommentThread } from '@/stores/commentThread'
import type { BUDPriority } from '@/types'
import type { CardUpdate } from '@/types/boards'
import { CARD_COMMENT_WIRE } from '@/utils/boardCardWire'

export function useBoardCardPage(number: Ref<number>) {
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
    onDoc: kind => void docs.refresh(kind),
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

  const nameFor = (id: string) => page.members.value.find(m => m.user_id === id)?.name ?? directory.nameFor(id)
  const photoFor = (id: string) => page.members.value.find(m => m.user_id === id)?.avatar_url ?? directory.photoFor(id)

  /** Report an action's result; true when it worked. */
  async function act(pending: Promise<string | null>, success: string): Promise<boolean> {
    const error = await pending
    if (!feedback.fail(error)) feedback.announce(success)
    return !error
  }

  const key = () => detail.value?.key ?? ''
  const save = (patch: CardUpdate, success: string) => act(edits.update(patch), success)

  const actions = {
    saveTitle: (title: string) => save({ title }, 'Title saved'),
    saveDescription: (text: string) => save({ description_md: text || null }, 'Description saved'),
    setPriority: (priority: BUDPriority | null) => save({ priority }, priority ? `Priority set to ${priority}` : 'Priority cleared'),
    setAssignees: (ids: string[]) => save({ assignee_ids: ids }, 'Assignees saved'),
    setLabels: (ids: string[]) => save({ label_ids: ids }, 'Labels saved'),
    saveDate: (field: 'start_at' | 'due_at', iso: string | null) =>
      save({ [field]: iso }, `${field === 'due_at' ? 'Due' : 'Start'} date ${iso ? 'saved' : 'cleared'}`),
    setDueDone: (done: boolean) => save({ due_done: done }, done ? 'Marked done' : 'Marked not done'),
    move: (stageId: string) =>
      act(edits.moveTo(stageId), `Moved ${key()} to ${stages.value.find(s => s.id === stageId)?.name ?? 'the stage'}`),
    restore: () => act(edits.restore(), `Restored ${key()}`),
    async archive(): Promise<void> {
      const archivedKey = key()
      if (feedback.fail(await edits.archive())) return
      feedback.show({ text: `Archived ${archivedKey}`, action: { label: 'Undo', run: () => void actions.restore() } })
    },
    result: (error: string | null, success: string) => {
      if (!feedback.fail(error)) feedback.announce(success)
    },
  }

  onMounted(() => {
    void directory.ensureLoaded()
    void boardsStore.ensureLimits()
  })

  return {
    card, page, detail, boardKey, feedback, checklist, activity, thread, attachments,
    canEdit, canMove, canComment, canArchive, stages, stage, limits, nameFor, photoFor, actions,
  }
}
