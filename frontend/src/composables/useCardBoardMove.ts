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

// The "Move to another board" dialog's state, the same from the board and
// the card's page: the boards I edit (from GET /boards), the chosen board
// (useMoveTarget), its stages as the arriving card meets them (locked ones
// say why; a locked server pick gives way to the first stage that takes
// the card), and the move itself under the target stage's entry rules
// (useStageEntry). A stage the move itself leaves unreachable says so and
// offers another stage. A rate-limited move waits out the server's
// Retry-After; a target that went away is dropped from the list. What a
// refusal says stays in the dialog (its own feedback), not on the page.

import { isAxiosError } from 'axios'
import { computed, ref, watch } from 'vue'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useMoveTarget } from '@/composables/useMoveTarget'
import { useRetryCountdown } from '@/composables/useRetryCountdown'
import { useStageEntry } from '@/composables/useStageEntry'
import { boardsApi } from '@/services/boardsApi'
import type { BoardDetail, BoardPersonRead, CardDetail, CardSummary, CustomBoardItem, StageRequiredField } from '@/types/boards'
import { arriving, moveChanges, moveTargets, type MoveSource } from '@/utils/boardMove'
import { moveError, moveLost, waitWords, type MoveLost } from '@/utils/boardMoveErrors'
import { landingNote, moveDeadEnd, moveLanding, moveStageItems, openStage, type MoveLanding } from '@/utils/boardMoveStages'
import { entryRefusal } from '@/utils/entryRefusal'
import { extractApiError } from '@/utils/errors'
import { retryAfterOf } from '@/utils/importErrors'
import { logFailure } from '@/utils/logFailure'

interface Options {
  card: () => CardSummary | null
  board: () => BoardDetail | null
  people: () => BoardPersonRead[]
  /** The refusal's action ("Open card", "Show me"). */
  fixLabel: string
  fix: (field: StageRequiredField) => void
}

const RATE_LIMITED = 429

export function useCardBoardMove(o: Options) {
  const feedback = useBoardFeedback()
  const countdown = useRetryCountdown()
  const boards = ref<CustomBoardItem[]>([])
  const listing = ref(false)
  const listError = ref('')
  const targetKey = ref<string | null>(null)
  const stageId = ref<string | null>(null)
  /** The stage picker's menu, opened by "Pick another stage". */
  const stageMenu = ref(false)
  const busy = ref(false)
  /** The card left this board (moved or deleted) since the dialog opened. */
  const cardGone = ref(false)
  const landing = ref<MoveLanding | null>(null)
  const { target, loading, failed, load } = useMoveTarget()

  const fromStage = () => o.board()?.stages.find(s => s.id === o.card()?.stage_id) ?? null
  const entry = useStageEntry({
    // The source stage too, so entering Done from Done isn't completing the card again.
    stages: () => {
      const from = fromStage()
      return [...(target.value?.stages ?? []), ...(from ? [from] : [])]
    },
    feedback,
    fixLabel: o.fixLabel,
    fix: (_card, _stage, missing) => o.fix(missing[0]),
  })

  const source = computed<MoveSource | null>(() => {
    const card = o.card()
    const board = o.board()
    return card && board ? { card, labels: board.labels, people: o.people() } : null
  })
  const changes = computed(() => (source.value && target.value ? moveChanges(source.value, target.value) : []))
  const stages = computed(() => (source.value && target.value ? moveStageItems(source.value, target.value) : []))
  /** Why the preselected stage isn't the server's pick, while it's still the one picked. */
  const stageNote = computed(() => {
    const l = landing.value
    if (!l || !source.value || !target.value || l.stage?.id !== stageId.value) return null
    return landingNote(source.value, target.value, l)
  })
  const waitNote = computed(() => (countdown.waiting.value ? waitWords(countdown.left.value) : ''))

  async function loadBoards(): Promise<void> {
    listError.value = ''
    listing.value = true
    try {
      boards.value = moveTargets((await boardsApi.list()).items, o.board()?.board.key ?? '')
    } catch (err) {
      listError.value = extractApiError(err, "Couldn't load your boards. Try again.")
      logFailure('boards', 'move boards fetch', err)
    } finally {
      listing.value = false
    }
  }

  /** Open the dialog afresh: nothing picked, my boards listed. */
  async function start(): Promise<void> {
    targetKey.value = null
    cardGone.value = false
    feedback.toastOpen.value = false
    await loadBoards()
  }

  // Synchronous, so a refusal shown right after a reset isn't cleared by it.
  watch(targetKey, key => {
    stageId.value = null
    landing.value = null
    feedback.toastOpen.value = false
    void load(key)
  }, { flush: 'sync' })
  watch(target, t => {
    if (!t || !source.value) return
    landing.value = moveLanding(source.value, t, fromStage())
    stageId.value = landing.value.stage?.id ?? null
  })
  watch(stageId, () => (feedback.toastOpen.value = false), { flush: 'sync' })

  /** The chosen stage can't take the card because of the move itself: say so, offer another stage. */
  function deadEnd(src: MoveSource, sid: string): boolean {
    const t = target.value
    const stage = t?.stages.find(s => s.id === sid)
    const text = t && stage ? moveDeadEnd(src, t, stage) : null
    if (!t || !text) return false
    const other = openStage(src, t)
    const action = other ? { label: 'Pick another stage', run: () => (stageMenu.value = true) } : undefined
    feedback.show({ text, error: true, persist: true, action })
    feedback.announce(text)
    return true
  }

  /** After the move went nowhere: the card is gone, or the board is (drop it, list mine again). */
  function lost(what: MoveLost | null, text: string): void {
    if (what === 'card') cardGone.value = true
    if (what !== 'board') return
    targetKey.value = null
    feedback.fail(text)
    void loadBoards()
  }

  /** Send the move; resolves to the card on its new board, or null when it didn't go. */
  async function move(): Promise<CardDetail | null> {
    const t = target.value
    const src = source.value
    const fromKey = o.board()?.board.key
    const sid = stageId.value
    if (!t || !src || !fromKey || !sid || busy.value || deadEnd(src, sid)) return null
    feedback.toastOpen.value = false
    busy.value = true
    let what: MoveLost | null = null
    let said = ''
    try {
      const sent = await entry.enter(arriving(src, t), sid, async confirm => {
        const body = { target_board_key: t.key, stage_id: sid, confirm_open_checklist: confirm }
        try {
          return { error: null, card: await boardsApi.moveCardToBoard(fromKey, src.card.number, body) }
        } catch (err) {
          const wait = isAxiosError(err) && err.response?.status === RATE_LIMITED ? retryAfterOf(err) : null
          if (wait) countdown.wait(wait)
          what = moveLost(err)
          said = moveError(err, t.name, src.card.key)
          return { error: wait ? null : said, refusal: entryRefusal(err), card: null }
        }
      })
      if (!sent?.card) lost(what, said)
      return sent?.card ?? null
    } finally {
      busy.value = false
    }
  }

  const ready = computed(
    () => !!target.value && !!stageId.value && !busy.value && !countdown.waiting.value && !cardGone.value,
  )

  return {
    feedback, boards, listing, listError, targetKey, stageId, stageMenu, stages, stageNote, waitNote, target, loading,
    failed, changes, busy, ready, cardGone, confirm: entry.confirm, start, move, retry: () => load(targetKey.value),
  }
}

export type CardBoardMove = ReturnType<typeof useCardBoardMove>
