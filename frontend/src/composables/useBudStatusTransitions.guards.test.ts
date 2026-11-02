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
 * The guards in front of a stage change: no open PR for code review, a
 * reason to skip unmerged PRs, unfinished manual test cases before UAT or
 * prod, and the backend's refusal shown as a snackbar. Also cancelling a
 * running agent or design.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { BUDDocument, BUDStatus } from '@/types'
import { trackResultSave } from '@/stores/manualResultSaves'
import { STATUS_TAB_MAP } from '@/utils/budDetail'

const store = vi.hoisted(() => ({
  error: '',
  updateBUD: vi.fn(),
  fetchCodeReviewStatus: vi.fn(),
  refreshBUDIfCurrent: vi.fn(),
  cancelAgentTask: vi.fn(),
  cancelDesign: vi.fn(),
}))
vi.mock('@/stores/bud', () => ({ useBUDStore: () => store }))

import { useBudStatusTransitions } from '@/composables/useBudStatusTransitions'

let bud: BUDDocument | null
const setActiveTab = vi.fn()
const onStatusChanged = vi.fn(async () => undefined)

function at(status: BUDStatus, extra: Record<string, unknown> = {}) {
  bud = { id: 'bud-1', status, ...extra } as unknown as BUDDocument
  return useBudStatusTransitions({
    getBud: () => bud,
    // As the BUD page does: refresh the open BUD, then read it again.
    refreshBud: async (id: string) => {
      await store.refreshBUDIfCurrent(id)
      return bud
    },
    setActiveTab,
    getStatusTabMap: () => STATUS_TAB_MAP,
    onStatusChanged,
  })
}

function prs(...states: string[]) {
  store.fetchCodeReviewStatus.mockResolvedValue({ repos: states.map(pr_state => ({ pr_state })) })
}

beforeEach(() => {
  vi.clearAllMocks()
  store.error = ''
  store.updateBUD.mockResolvedValue({})
  store.refreshBUDIfCurrent.mockResolvedValue(undefined)
})

describe('entering code review', () => {
  it('warns when no PR is open, and moves only once confirmed', async () => {
    prs('merged', 'closed')
    const c = at('development')
    await c.updateStatus('code_review')
    expect(c.showNoPRWarningDialog.value).toBe(true)
    expect(store.updateBUD).not.toHaveBeenCalled()

    await c.confirmNoPRWarning()
    expect(c.showNoPRWarningDialog.value).toBe(false)
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', { status: 'code_review' })
    expect(setActiveTab).toHaveBeenCalledWith('code-review', expect.objectContaining({ id: 'bud-1' }))
  })

  it('moves straight on with an open PR', async () => {
    prs('open')
    const c = at('development')
    await c.updateStatus('code_review')
    expect(c.showNoPRWarningDialog.value).toBe(false)
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', { status: 'code_review' })
    expect(onStatusChanged).toHaveBeenCalled()
  })
})

describe('code review to testing', () => {
  it('passes straight through when every PR is merged', async () => {
    prs('merged', 'merged')
    await at('code_review').updateStatus('testing')
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', { status: 'testing' })
  })

  it.each([[['merged', 'open']], [[]]])('asks for a reason with PRs %j', async (states) => {
    prs(...states)
    const c = at('code_review')
    await c.updateStatus('testing')
    expect(c.overrideReasonDialog.value).toBe(true)
    expect(store.updateBUD).not.toHaveBeenCalled()
  })

  it('refuses a blank reason and records a real one', async () => {
    prs('open')
    const c = at('code_review')
    await c.updateStatus('testing')
    c.overrideReasonText.value = '   '
    await c.confirmOverrideStatus()
    expect(c.overrideReasonDialog.value).toBe(true)
    expect(store.updateBUD).not.toHaveBeenCalled()

    c.overrideReasonText.value = '  docs-only change '
    await c.confirmOverrideStatus()
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', {
      status: 'testing', status_override_reason: 'docs-only change',
    })
  })
})

describe('leaving testing', () => {
  it('lists the manual cases still pending, from a fresh copy of the BUD', async () => {
    const c = at('testing', { qa_manual_cases: [] })
    store.refreshBUDIfCurrent.mockImplementation(async () => {
      bud = { ...bud!, qa_manual_cases: [
        { id: 't1', title: 'Login works', result: 'pass' },
        { id: 't2', title: 'Refund flow', result: 'pending' },
      ] } as unknown as BUDDocument
    })
    await c.updateStatus('uat')
    expect(store.refreshBUDIfCurrent).toHaveBeenCalledWith('bud-1')
    expect(c.showPendingCasesDialog.value).toBe(true)
    expect(c.pendingCasesTarget.value).toBe('uat')
    expect(c.pendingCasesList.value).toEqual([{ id: 't2', title: 'Refund flow' }])
    expect(store.updateBUD).not.toHaveBeenCalled()

    c.openQATab()
    expect(c.showPendingCasesDialog.value).toBe(false)
    expect(setActiveTab).toHaveBeenCalledWith('testing', expect.objectContaining({ id: 'bud-1' }))
  })

  it('reads the cases only after a result still saving has landed', async () => {
    const c = at('testing', { qa_manual_cases: [] })
    let land!: () => void
    void trackResultSave('bud-1', new Promise<void>(resolve => { land = resolve }))
    const moving = c.updateStatus('uat')
    await Promise.resolve()
    expect(store.refreshBUDIfCurrent).not.toHaveBeenCalled()
    land()
    await moving
    expect(store.refreshBUDIfCurrent).toHaveBeenCalledWith('bud-1')
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', { status: 'uat' })
  })

  it('moves to prod when no case is pending', async () => {
    const c = at('testing', { qa_manual_cases: [{ id: 't1', title: 'x', result: 'fail' }] })
    await c.updateStatus('prod')
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', { status: 'prod' })
    expect(setActiveTab).toHaveBeenCalledWith('prod', expect.objectContaining({ id: 'bud-1' }))
  })
})

describe('a refused stage change', () => {
  it("shows the server's reason and stays on the current tab", async () => {
    store.updateBUD.mockImplementation(async () => {
      store.error = 'Manual test cases still pending'
      return null
    })
    const c = at('bud')
    await c.updateStatus('design')
    expect(c.statusErrorSnackbar.value).toBe(true)
    expect(c.statusErrorMessage.value).toBe('Manual test cases still pending')
    expect(setActiveTab).not.toHaveBeenCalled()
    expect(onStatusChanged).not.toHaveBeenCalled()
    expect(c.changingStatus.value).toBe(false)
  })

  it('does nothing before the BUD has loaded', async () => {
    const c = at('bud')
    bud = null
    await c.updateStatus('design')
    expect(store.updateBUD).not.toHaveBeenCalled()
  })
})

describe('cancelling', () => {
  it('cancels the running agent and says so', async () => {
    const c = at('tech_arch', { active_agent_task: { id: 'task-9' } })
    await c.cancelRunningAgent()
    expect(store.cancelAgentTask).toHaveBeenCalledWith('bud-1', 'task-9')
    expect(c.statusInfoMessage.value).toBe('Cancelled')
    expect(c.cancellingAgent.value).toBe(false)
  })

  it('does nothing without a running agent', async () => {
    await at('tech_arch').cancelRunningAgent()
    expect(store.cancelAgentTask).not.toHaveBeenCalled()
  })

  it('shows why a design could not be cancelled', async () => {
    store.cancelDesign.mockImplementation(async () => { store.error = 'Already finished' })
    const c = at('design')
    await c.cancelDesign('d1')
    expect(store.cancelDesign).toHaveBeenCalledWith('bud-1', 'd1')
    expect(c.statusErrorMessage.value).toBe('Already finished')
    expect(c.statusInfoSnackbar.value).toBe(false)
    expect(c.cancellingDesignId.value).toBeNull()
  })
})

describe('the BUD a change is about', () => {
  it('is the one asked about, even if the page moves to another while it checks', async () => {
    prs('open')
    const c = at('code_review')
    const asked = c.updateStatus('testing')
    bud = { id: 'bud-2', status: 'design' } as unknown as BUDDocument
    await asked
    expect(c.overrideReasonDialog.value).toBe(true)
    c.overrideReasonText.value = 'Docs only'
    await c.confirmOverrideStatus()
    expect(store.updateBUD).toHaveBeenCalledWith('bud-1', { status: 'testing', status_override_reason: 'Docs only' })
  })

  it('takes no new change while a dialog waits on the last one', async () => {
    const c = at('prod')
    await c.updateStatus('closed')
    expect(c.showCloseConfirmDialog.value).toBe(true)
    await c.updateStatus('testing')
    expect(c.busy.value).toBe(true)
    await c.confirmClose()
    expect(store.updateBUD.mock.calls).toEqual([['bud-1', { status: 'closed' }]])
  })
})
