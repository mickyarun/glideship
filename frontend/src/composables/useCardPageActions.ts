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

// What a card's page does when I act, and what it says back: a live-region
// announcement on success (and a fresh history, since the live channel
// skips this tab's own changes), the snackbar on failure, and Undo after a
// stage move, an archive or a deleted checklist line. Stage moves keep to
// the stage's entry rules (useStageEntry); a refused one offers "Show me",
// which brings the first missing field into view here.

import type { ComputedRef } from 'vue'
import type { BoardCard } from '@/composables/useBoardCard'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { useCardActivity } from '@/composables/useCardActivity'
import type { useCardChecklist } from '@/composables/useCardChecklist'
import type { useCardEdits } from '@/composables/useCardEdits'
import { useStageEntry } from '@/composables/useStageEntry'
import type { BUDPriority } from '@/types'
import type { CardUpdate, ChecklistItem, StageRead, StageRequiredField } from '@/types/boards'

interface Parts {
  card: BoardCard
  edits: ReturnType<typeof useCardEdits>
  checklist: ReturnType<typeof useCardChecklist>
  activity: ReturnType<typeof useCardActivity>
  feedback: ReturnType<typeof useBoardFeedback>
  stages: ComputedRef<StageRead[]>
  /** Bring a field the stage needs into view on this page. */
  showField: (field: StageRequiredField) => void
}

export function useCardPageActions({ card, edits, checklist, activity, feedback, stages, showField }: Parts) {
  const key = () => card.detail.value?.key ?? ''
  const stageName = (id: string) => stages.value.find(s => s.id === id)?.name ?? 'the stage'

  /** Report an action's result; true when it worked. */
  async function act(pending: Promise<string | null>, success: string): Promise<boolean> {
    const error = await pending
    if (feedback.fail(error)) return false
    feedback.announce(success)
    activity.refresh()
    return true
  }

  const save = (patch: CardUpdate, success: string) => act(edits.update(patch), success)
  const entry = useStageEntry({ stages: () => stages.value, feedback, fixLabel: 'Show me', fix: (_, f) => showField(f) })

  async function move(stageId: string, { undoable = true } = {}): Promise<boolean> {
    const held = card.detail.value
    const from = held?.stage_id
    const movedKey = key()
    if (!held || !from || from === stageId) return true
    if (!(await entry.enter(held, stageId, confirm => edits.moveTo(stageId, confirm)))) return false
    feedback.announce(`Moved ${movedKey} to ${stageName(stageId)}`)
    activity.refresh()
    if (undoable) {
      feedback.show({
        text: `Moved ${movedKey} to ${stageName(stageId)}`,
        action: { label: 'Undo', run: () => void move(from, { undoable: false }) },
      })
    }
    return true
  }

  const restore = () => act(edits.restore(), `Restored ${key()}`)

  async function archive(): Promise<void> {
    const archivedKey = key()
    if (feedback.fail(await edits.archive())) return
    activity.refresh()
    feedback.show({ text: `Archived ${archivedKey}`, action: { label: 'Undo', run: () => void restore() } })
  }

  async function removeItem(item: ChecklistItem): Promise<boolean> {
    const at = checklist.items.value.findIndex(i => i.id === item.id)
    if (feedback.fail(await checklist.remove(item))) return false
    activity.refresh()
    feedback.show({
      text: `Deleted ${item.text}`,
      action: { label: 'Undo', run: () => void act(checklist.restore(item, at), `Put back ${item.text}`) },
    })
    return true
  }

  const repoSaved = (id: string | null) => (id ? 'Repository saved' : 'Repository cleared')

  return {
    confirm: entry.confirm,
    setRepo: (repoId: string | null) => save({ repo_id: repoId }, repoSaved(repoId)),
    saveTitle: (title: string) => save({ title }, 'Title saved'),
    saveDescription: (text: string) => save({ description_md: text || null }, 'Description saved'),
    setPriority: (priority: BUDPriority | null) =>
      save({ priority }, priority ? `Priority set to ${priority}` : 'Priority cleared'),
    setAssignees: (ids: string[]) => save({ assignee_ids: ids }, 'Assignees saved'),
    setLabels: (ids: string[]) => save({ label_ids: ids }, 'Labels saved'),
    saveDate: (field: 'start_at' | 'due_at', iso: string | null) =>
      save({ [field]: iso }, `${field === 'due_at' ? 'Due' : 'Start'} date ${iso ? 'saved' : 'cleared'}`),
    setDueDone: (done: boolean) => save({ due_done: done }, done ? 'Marked done' : 'Marked not done'),
    move: (stageId: string) => move(stageId),
    restore,
    archive,
    removeItem,
    copied: (ok: boolean) => (ok ? feedback.announce('Link copied') : feedback.fail("Couldn't copy the link")),
    result: (error: string | null, success: string) => {
      if (feedback.fail(error)) return
      feedback.announce(success)
      activity.refresh()
    },
    /** A document changed here: the card's facts (has a PRD) follow. */
    docResult: (error: string | null, success: string) => {
      if (feedback.fail(error)) return
      feedback.announce(success)
      activity.refresh()
      void edits.refresh()
    },
  }
}

export type CardPageActions = ReturnType<typeof useCardPageActions>
