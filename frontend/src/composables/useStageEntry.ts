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
// lacks refuses at once (no request) and says what's missing (on the
// snackbar, which waits for me, and to screen readers), with an action to
// go and fill it in; completing a card with checklist
// items open asks first and then sends the move with the confirmation. The
// server checks both too: its 422 is reported the same way, and its 409
// (the board's copy of the checklist was stale) asks and resends.

import { ref, shallowRef } from 'vue'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import type { CardSummary, StageRead, StageRequiredField } from '@/types/boards'
import type { EntryRefusal } from '@/utils/entryRefusal'
import { checklistQuestion, completes, missingFor, needsSentence, openItems } from '@/utils/stageRules'

type Feedback = ReturnType<typeof useBoardFeedback>

const UNKNOWN_STAGE = 'that stage'

export interface EntryResult {
  error: string | null
  refusal?: EntryRefusal | null
}

interface Options {
  stages: () => StageRead[]
  feedback: Feedback
  /** The snackbar action that takes me to the missing fields ("Open card"). */
  fixLabel: string
  fix: (card: CardSummary, stage: StageRead, missing: StageRequiredField[]) => void
  /** Open the card's page (offered beside the checklist question); left out on the page itself. */
  openCard?: (card: CardSummary) => void
  /** Told of every refusal, to show it beside the stage too. */
  onRefuse?: (card: CardSummary, stage: StageRead, missing: StageRequiredField[]) => void
}

/** A yes/no question about an open checklist, answered by ChecklistConfirmDialog. */
export function useChecklistConfirm() {
  const asking = ref(false)
  const question = ref('')
  /** Opens the card instead, when the dialog offers that. */
  const opener = shallowRef<(() => void) | null>(null)
  let settle: ((yes: boolean) => void) | null = null

  function ask(text: string, open: (() => void) | null = null): Promise<boolean> {
    settle?.(false)
    question.value = text
    opener.value = open
    asking.value = true
    return new Promise(resolve => (settle = resolve))
  }

  function answer(yes: boolean): void {
    asking.value = false
    const done = settle
    settle = null
    done?.(yes)
  }

  /** "Open card": no move, and the card's page instead. */
  function openCard(): void {
    const open = opener.value
    answer(false)
    open?.()
  }

  return { asking, question, opener, ask, answer, openCard }
}

export type ChecklistConfirm = ReturnType<typeof useChecklistConfirm>

export function useStageEntry(o: Options) {
  const confirm = useChecklistConfirm()
  const stageOf = (id: string) => o.stages().find(s => s.id === id) ?? null

  function refuse(card: CardSummary, stage: StageRead, missing: StageRequiredField[]): void {
    const text = needsSentence(stage.name, missing)
    o.feedback.show({
      text,
      action: missing.length ? { label: o.fixLabel, run: () => o.fix(card, stage, missing) } : undefined,
      persist: true,
    })
    o.feedback.announce(text)
    o.onRefuse?.(card, stage, missing)
  }

  const askAbout = (card: CardSummary, stageName: string, open: number, total: number) =>
    confirm.ask(checklistQuestion(open, total, card.key, stageName), o.openCard ? () => o.openCard?.(card) : null)

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
    // Reordering inside a stage isn't entering it; a stage this tab doesn't
    // know yet is left to the server, whose refusals are handled the same.
    const entering = stage && card.stage_id !== stageId ? stage : null
    const missing = entering ? missingFor(card, entering) : []
    if (entering && missing.length) {
      refuse(card, entering, missing)
      return null
    }
    let confirmed = false
    const open = openItems(card)
    if (entering && open && completes(entering, stageOf(card.stage_id))) {
      if (!(await askAbout(card, entering.name, open, card.checklist_total))) return null
      confirmed = true
    }
    let result = await send(confirmed)
    const refusal = result.refusal
    if (refusal?.code === 'CHECKLIST_OPEN' && !confirmed) {
      if (!(await askAbout(card, stage?.name ?? UNKNOWN_STAGE, refusal.open, refusal.total))) return null
      result = await send(true)
    }
    // The server names the stage it checked, which this tab may have had wrong.
    const refused = result.refusal?.code === 'STAGE_REQUIREMENTS_MISSING' ? result.refusal : null
    const named = refused ? stageOf(refused.stageId) ?? stage : null
    if (refused && named) {
      refuse(card, named, refused.missing)
      return null
    }
    return o.feedback.fail(result.error) ? null : result
  }

  return { confirm, enter, refuse }
}
