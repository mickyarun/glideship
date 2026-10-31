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

// Moving a card into a stage under the stage's entry rules, the same from a
// drag, the card's menu and its page: a stage that needs fields the card
// lacks refuses at once (no request) and says what's missing, with an
// action to go and fill in the first one; completing a card with checklist
// items open asks first and then sends the move with the confirmation. The
// server checks both too: its 422 is reported the same way, and its 409
// (the board's copy of the checklist was stale) asks and resends.

import { ref } from 'vue'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardSummary, StageRead, StageRequiredField } from '@/types/boards'
import type { EntryRefusal } from '@/utils/entryRefusal'
import { checklistQuestion, completes, missingFor, needsSentence, openItems } from '@/utils/stageRules'

type Feedback = ReturnType<typeof useBoardFeedback>

export interface EntryResult {
  error: string | null
  refusal?: EntryRefusal | null
}

interface Options {
  stages: () => StageRead[]
  feedback: Feedback
  /** The snackbar action that takes me to a missing field ("Open card"). */
  fixLabel: string
  fix: (card: CardSummary, field: StageRequiredField) => void
}

/** A yes/no question about an open checklist, answered by ChecklistConfirmDialog. */
export function useChecklistConfirm() {
  const asking = ref(false)
  const question = ref('')
  let settle: ((yes: boolean) => void) | null = null

  function ask(text: string): Promise<boolean> {
    settle?.(false)
    question.value = text
    asking.value = true
    return new Promise(resolve => (settle = resolve))
  }

  function answer(yes: boolean): void {
    asking.value = false
    const done = settle
    settle = null
    done?.(yes)
  }

  return { asking, question, ask, answer }
}

export type ChecklistConfirm = ReturnType<typeof useChecklistConfirm>

export function useStageEntry(o: Options) {
  const confirm = useChecklistConfirm()
  const stageOf = (id: string) => o.stages().find(s => s.id === id) ?? null

  function refuse(card: CardSummary, stage: StageRead, missing: StageRequiredField[]): void {
    const first = missing[0]
    o.feedback.show({
      text: needsSentence(stage.name, missing),
      action: first ? { label: o.fixLabel, run: () => o.fix(card, first) } : undefined,
    })
  }

  const askAbout = (card: CardSummary, stage: StageRead, open: number, total: number) =>
    confirm.ask(checklistQuestion(open, total, card.key, stage.name))

  /**
   * Move card to stageId through send (true: confirm the open
   * checklist). Resolves to the move's result, or null when the rules
   * refused it or I said no; the error is reported either way.
   */
  async function enter<R extends EntryResult>(
    card: CardSummary,
    stageId: string,
    send: (confirmOpenChecklist: boolean) => Promise<R>,
  ): Promise<R | null> {
    const stage = stageOf(stageId)
    // Reordering inside a stage isn't entering it.
    if (!stage || card.stage_id === stageId) {
      const result = await send(false)
      return o.feedback.fail(result.error) ? null : result
    }
    const missing = missingFor(card, stage)
    if (missing.length) {
      refuse(card, stage, missing)
      return null
    }
    let confirmed = false
    const open = openItems(card)
    if (open && completes(stage, stageOf(card.stage_id))) {
      if (!(await askAbout(card, stage, open, card.checklist_total))) return null
      confirmed = true
    }
    let result = await send(confirmed)
    const refusal = result.refusal
    if (refusal?.code === 'CHECKLIST_OPEN' && !confirmed) {
      if (!(await askAbout(card, stage, refusal.open, refusal.total))) return null
      result = await send(true)
    }
    if (result.refusal?.code === 'STAGE_REQUIREMENTS_MISSING') {
      refuse(card, stage, result.refusal.missing)
      return null
    }
    return o.feedback.fail(result.error) ? null : result
  }

  return { confirm, enter }
}
