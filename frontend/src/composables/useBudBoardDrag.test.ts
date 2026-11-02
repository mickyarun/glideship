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

/**
 * Dragging BUDs on the Delivery board: which stages a dragged BUD can't
 * enter and why, a drop running the BUD page's stage-change guards, and a
 * refused drop saying why with the BUD page as the way on.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import { useBoardFeedback } from '@/composables/useBoardFeedback'
import { dragBlocks, dragging } from '@/composables/useCardDrag'
import { BUD_STATUS_ORDER, type BUDListItem, type BUDStatus } from '@/types'

const store = vi.hoisted(() => ({
  buds: [] as BUDListItem[],
  designAvailableFor: null as string | null,
  error: '',
  updateBUD: vi.fn(),
  peekBUD: vi.fn(),
  fetchCodeReviewStatus: vi.fn(),
  refreshBUDIfCurrent: vi.fn(),
}))
const perms = vi.hoisted(() => ({ granted: new Set<string>(['buds:edit']) }))
const push = vi.hoisted(() => vi.fn())
vi.mock('@/stores/bud', () => ({ useBUDStore: () => store }))
vi.mock('@/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (p: string) => perms.granted.has(p) }),
}))
vi.mock('@/composables/usePhaseOrder', () => ({ usePhaseOrder: () => ({ phaseOrder: ref(BUD_STATUS_ORDER) }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import { useBudBoardDrag } from '@/composables/useBudBoardDrag'

const COLUMNS = BUD_STATUS_ORDER.filter(s => s !== 'discarded')

function bud(status: BUDStatus, extra: Partial<BUDListItem> = {}): BUDListItem {
  return { id: 'b2', bud_number: 2, title: 'Saved filters', status, has_prd: true, has_tech_spec: true, ...extra } as BUDListItem
}

function board(...buds: BUDListItem[]) {
  store.buds = buds
  const feedback = useBoardFeedback()
  return { feedback, drag: useBudBoardDrag(ref(COLUMNS), feedback) }
}

const drop = (stageId: string) => ({ cardId: 'b2', stageId, index: 0 })

beforeEach(() => {
  vi.clearAllMocks()
  perms.granted = new Set(['buds:edit'])
  store.error = ''
  store.designAvailableFor = null
  store.updateBUD.mockResolvedValue({})
})
afterEach(() => {
  dragging.value = null
})

describe('while a BUD is dragged', () => {
  it('marks each stage it cannot enter, and says so once', async () => {
    const { drag, feedback } = board(bud('bud', { has_prd: false }))
    dragging.value = { cardId: 'b2', fromStageId: 'bud', overStageId: 'bud' }
    await nextTick()
    expect(drag.blocks.value.design).toBe('Needs a PRD')
    expect(drag.blocks.value.development).toBe('One stage at a time')
    expect(dragBlocks.value).toEqual(drag.blocks.value)
    await nextTick()
    expect(feedback.announcement.value).toBe("BUD-002 can't move from here. Design needs a PRD first.")
  })

  it('marks nothing once the drag ends', async () => {
    const { drag } = board(bud('bud'))
    dragging.value = { cardId: 'b2', fromStageId: 'bud', overStageId: 'bud' }
    dragging.value = null
    expect(drag.blocks.value).toEqual({})
    expect(dragBlocks.value).toEqual({})
  })
})

describe('a drop', () => {
  it('moves the BUD one stage on and says where', async () => {
    const { drag, feedback } = board(bud('design'))
    drag.drop(drop('tech_arch'))
    await vi.waitFor(() => expect(store.updateBUD).toHaveBeenCalledWith('b2', { status: 'tech_arch' }))
    await nextTick()
    expect(feedback.announcement.value).toBe('Moved BUD-002 to Tech Architecture')
  })

  it('does nothing in the BUD\'s own stage', () => {
    const { drag, feedback } = board(bud('design'))
    drag.drop(drop('design'))
    expect(store.updateBUD).not.toHaveBeenCalled()
    expect(feedback.toast.value).toBeNull()
  })

  it('refuses a skip, with the BUD page as the way on', () => {
    const { drag, feedback } = board(bud('design'))
    drag.drop(drop('development'))
    expect(store.updateBUD).not.toHaveBeenCalled()
    expect(feedback.toast.value?.text).toBe('BUD-002 moves one stage at a time. Open it to move it to Development.')
    expect(feedback.toast.value?.persist).toBe(true)
    feedback.toast.value?.action?.run()
    expect(push).toHaveBeenCalledWith({ path: '/buds/b2', query: undefined })
  })

  it('reports letting go over a stage it cannot enter', () => {
    const { drag, feedback } = board(bud('tech_arch', { has_tech_spec: false }))
    drag.blocked('b2', 'development')
    expect(feedback.toast.value?.text).toBe('Development needs a tech spec first.')
  })

  it('asks before closing, and closes once confirmed', async () => {
    const { drag } = board(bud('prod'))
    drag.drop(drop('closed'))
    await vi.waitFor(() => expect(drag.status.showCloseConfirmDialog.value).toBe(true))
    expect(store.updateBUD).not.toHaveBeenCalled()
    await drag.status.confirmClose()
    expect(store.updateBUD).toHaveBeenCalledWith('b2', { status: 'closed' })
  })

  it('stops at unfinished test cases, read fresh, and opens the BUD on its QA tab', async () => {
    store.peekBUD.mockResolvedValue({ id: 'b2', status: 'testing', qa_manual_cases: [{ id: 'TM-1', title: 'Login', result: 'pending' }] })
    const { drag } = board(bud('testing'))
    drag.drop(drop('uat'))
    await vi.waitFor(() => expect(drag.status.showPendingCasesDialog.value).toBe(true))
    expect(store.peekBUD).toHaveBeenCalledWith('b2')
    expect(store.updateBUD).not.toHaveBeenCalled()
    drag.status.openQATab()
    expect(push).toHaveBeenCalledWith({ path: '/buds/b2', query: { tab: 'testing' } })
  })

  it('moves the BUD it was dropped, even when another is dropped while it checks', async () => {
    let answer: (v: unknown) => void = () => undefined
    store.peekBUD.mockReturnValue(new Promise(ok => (answer = ok)))
    const other = bud('design', { id: 'b3', bud_number: 3 })
    const { drag } = board(bud('testing'), other)
    drag.drop(drop('uat'))
    drag.drop({ cardId: 'b3', stageId: 'tech_arch', index: 0 })
    answer({ id: 'b2', status: 'testing', qa_manual_cases: [] })
    await vi.waitFor(() => expect(store.updateBUD).toHaveBeenCalled())
    expect(store.updateBUD.mock.calls).toEqual([['b2', { status: 'uat' }]])
  })

  it('closes only the BUD whose close it asked about, and says to wait meanwhile', async () => {
    const other = bud('development', { id: 'b3', bud_number: 3 })
    const { drag, feedback } = board(bud('prod'), other)
    drag.drop(drop('closed'))
    await vi.waitFor(() => expect(drag.status.showCloseConfirmDialog.value).toBe(true))
    drag.drop({ cardId: 'b3', stageId: 'code_review', index: 0 })
    expect(feedback.toast.value?.text).toBe('Wait for BUD-002 to finish moving.')
    await drag.status.confirmClose()
    expect(store.updateBUD.mock.calls).toEqual([['b2', { status: 'closed' }]])
  })

  it('leaves starting designs to whoever opens the BUD', async () => {
    store.updateBUD.mockImplementation(async (id: string) => {
      store.designAvailableFor = id
      return {}
    })
    const { drag } = board(bud('bud'))
    drag.drop(drop('design'))
    await vi.waitFor(() => expect(store.updateBUD).toHaveBeenCalled())
    await vi.waitFor(() => expect(store.designAvailableFor).toBeNull())
  })

  it('warns before code review when no PR is open', async () => {
    store.fetchCodeReviewStatus.mockResolvedValue({ repos: [{ pr_state: 'merged' }] })
    const { drag } = board(bud('development'))
    drag.drop(drop('code_review'))
    await vi.waitFor(() => expect(drag.status.showNoPRWarningDialog.value).toBe(true))
    expect(store.updateBUD).not.toHaveBeenCalled()
  })

  it('asks why when skipping unmerged PRs into testing, and sends the reason', async () => {
    store.fetchCodeReviewStatus.mockResolvedValue({ repos: [{ pr_state: 'open' }] })
    const { drag } = board(bud('code_review'))
    drag.drop(drop('testing'))
    await vi.waitFor(() => expect(drag.status.overrideReasonDialog.value).toBe(true))
    drag.status.overrideReasonText.value = 'Docs only'
    await drag.status.confirmOverrideStatus()
    expect(store.updateBUD).toHaveBeenCalledWith('b2', { status: 'testing', status_override_reason: 'Docs only' })
  })

  it('lets QA take a BUD out of testing, and nowhere else', async () => {
    perms.granted = new Set(['buds:test'])
    store.peekBUD.mockResolvedValue({ id: 'b2', status: 'testing', qa_manual_cases: [] })
    const { drag, feedback } = board(bud('testing'))
    drag.drop(drop('code_review'))
    expect(feedback.toast.value?.text).toBe('You can only move BUDs out of Testing.')
    drag.drop(drop('uat'))
    await vi.waitFor(() => expect(store.updateBUD).toHaveBeenCalledWith('b2', { status: 'uat' }))
  })

  it('shows the server\'s words when it refuses', async () => {
    store.updateBUD.mockImplementation(async () => {
      // As extractApiError reads a coded refusal.
      store.error = 'A BUD needs a PRD before it can move to design.'
      return null
    })
    const { drag } = board(bud('bud'))
    drag.drop(drop('design'))
    await vi.waitFor(() => expect(drag.status.statusErrorSnackbar.value).toBe(true))
    expect(drag.status.statusErrorMessage.value).toBe('A BUD needs a PRD before it can move to design.')
  })
})

describe('the card menu', () => {
  it('moves the BUD like a drop, then puts focus on it in its new column', async () => {
    const { drag, feedback } = board(bud('design'))
    const focus = vi.spyOn(feedback, 'focusCard').mockResolvedValue(true)
    drag.menuMove(bud('design'), 'tech_arch')
    await vi.waitFor(() => expect(store.updateBUD).toHaveBeenCalledWith('b2', { status: 'tech_arch' }))
    await vi.waitFor(() => expect(focus).toHaveBeenCalledWith('b2'))
  })

  it('explains a locked stage, as a refused drop does', () => {
    const { drag, feedback } = board(bud('design'))
    drag.menuMove(bud('design'), 'development')
    expect(store.updateBUD).not.toHaveBeenCalled()
    expect(feedback.toast.value?.text).toBe('BUD-002 moves one stage at a time. Open it to move it to Development.')
  })

  it('gives each locked stage its note', () => {
    const { drag } = board(bud('bud', { has_prd: false }))
    expect(drag.blockFor(bud('bud', { has_prd: false }), 'design')).toBe('Needs a PRD')
    expect(drag.blockFor(bud('bud'), 'design')).toBeNull()
  })
})

describe('who can drag', () => {
  it('is anyone who can edit BUDs, or QA', () => {
    expect(board(bud('bud')).drag.canDrag.value).toBe(true)
    perms.granted = new Set(['buds:test'])
    expect(board(bud('bud')).drag.canDrag.value).toBe(true)
    perms.granted = new Set(['buds:view'])
    expect(board(bud('bud')).drag.canDrag.value).toBe(false)
  })
})
