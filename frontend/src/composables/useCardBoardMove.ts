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
// the card's page: the boards I edit (from GET /boards), the chosen
// board's stages, labels, people and repositories (fetched when it's
// picked, for the preview), the stage the server would pick, and the move
// itself under the target stage's entry rules (useStageEntry). What a
// refusal says stays in the dialog (its own feedback), not on the page.

import { computed, ref, watch } from 'vue'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useStageEntry } from '@/composables/useStageEntry'
import { boardsApi } from '@/services/boardsApi'
import type { BoardDetail, BoardPersonRead, CardDetail, CardSummary, CustomBoardItem, StageRequiredField } from '@/types/boards'
import { arriving, landingStage, moveChanges, moveError, moveTargets, type MoveSource, type MoveTarget } from '@/utils/boardMove'
import { entryRefusal } from '@/utils/entryRefusal'
import { extractApiError } from '@/utils/errors'
import { logFailure } from '@/utils/logFailure'

interface Options {
  card: () => CardSummary | null
  board: () => BoardDetail | null
  people: () => BoardPersonRead[]
  /** The refusal's action ("Open card", "Show me"). */
  fixLabel: string
  fix: (field: StageRequiredField) => void
}

/** The board a card is moving to, loaded when it's picked. */
function useMoveTarget() {
  const target = ref<MoveTarget | null>(null)
  const loading = ref(false)
  const failed = ref(false)
  let seq = 0

  async function load(key: string | null): Promise<void> {
    const mine = ++seq
    target.value = null
    failed.value = false
    loading.value = !!key
    if (!key) return
    try {
      const [detail, people, repos] = await Promise.all([boardsApi.get(key), boardsApi.people(key), boardsApi.repos(key)])
      if (mine !== seq) return
      const { board, stages, labels } = detail
      target.value = { key: board.key, name: board.name, stages, labels, people: people.items, repos: repos.items }
    } catch (err) {
      if (mine === seq) failed.value = true
      logFailure('boards', 'move target fetch', err)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  return { target, loading, failed, load }
}

export function useCardBoardMove(o: Options) {
  const feedback = useBoardFeedback()
  const boards = ref<CustomBoardItem[]>([])
  const listing = ref(false)
  const listError = ref('')
  const targetKey = ref<string | null>(null)
  const stageId = ref<string | null>(null)
  const busy = ref(false)
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

  /** Open the dialog afresh: nothing picked, my boards listed. */
  async function start(): Promise<void> {
    targetKey.value = null
    feedback.toastOpen.value = false
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

  watch(targetKey, key => {
    stageId.value = null
    feedback.toastOpen.value = false
    void load(key)
  })
  watch(target, t => {
    if (t) stageId.value = landingStage(t.stages, fromStage())?.id ?? null
  })
  watch(stageId, () => (feedback.toastOpen.value = false))

  /** Send the move; resolves to the card on its new board, or null when it didn't go. */
  async function move(): Promise<CardDetail | null> {
    const t = target.value
    const src = source.value
    const fromKey = o.board()?.board.key
    const sid = stageId.value
    if (!t || !src || !fromKey || !sid || busy.value) return null
    feedback.toastOpen.value = false
    busy.value = true
    try {
      const sent = await entry.enter(arriving(src, t), sid, async confirm => {
        const body = { target_board_key: t.key, stage_id: sid, confirm_open_checklist: confirm }
        try {
          return { error: null, card: await boardsApi.moveCardToBoard(fromKey, src.card.number, body) }
        } catch (err) {
          return { error: moveError(err, t.name), refusal: entryRefusal(err), card: null }
        }
      })
      return sent?.card ?? null
    } finally {
      busy.value = false
    }
  }

  const ready = computed(() => !!target.value && !!stageId.value && !busy.value)

  return {
    feedback, boards, listing, listError, targetKey, stageId, target, loading, failed, changes, busy, ready,
    confirm: entry.confirm, start, move, retry: () => load(targetKey.value),
  }
}

export type CardBoardMove = ReturnType<typeof useCardBoardMove>
