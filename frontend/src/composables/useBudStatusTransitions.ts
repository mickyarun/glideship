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
 * Status-transition orchestration for a BUD's stage changes, on the BUD
 * detail page and when a BUD is dragged on the Delivery board.
 *
 * Owns the guard logic (code_review → testing PR-merge check, testing
 * → uat/prod manual-cases check, no-open-PR warning for entering code
 * review), the three guard dialogs' state, the snackbar surfacing
 * backend rejections, and the cancel-running-agent handler.
 *
 * The "running status" banner that previously lived here was redundant
 * with the WS-driven "Assignment / Assigning {role}…" banner from
 * BUDWorkflowActions (skill_invoked) and was removed; only the guard
 * dialogs and the error snackbar render UI from this composable.
 *
 * Cross-cutting view dependencies (which BUD, its fresh read, active tab
 * switching, what follows a move) come in as hooks; the composable
 * doesn't reach into view-only refs directly.
 */

import { computed, ref } from 'vue'
import { useBUDStore } from '@/stores/bud'
import { resultSavesSettled } from '@/stores/manualResultSaves'
import type { BUDDocument } from '@/types'

/** What a stage change reads from the BUD it moves: a full BUD, or a board's list item. */
export type StatusSubject = Pick<BUDDocument, 'id' | 'status'>
  & Partial<Pick<BUDDocument, 'qa_manual_cases' | 'active_agent_task'>>

export interface BudStatusHooks {
  /** The BUD being moved; null while the page is still loading. */
  getBud: () => StatusSubject | null
  /** The BUD's latest read, for its manual test cases; null when it can't be read. */
  refreshBud: (id: string) => Promise<StatusSubject | null>
  /** Switch to a tab of the moved BUD — used by openQATab and the post-
   *  success tab sync after a successful PATCH. */
  setActiveTab: (tab: string, bud: StatusSubject) => void
  /** Status → tab mapping owned by the view (single source of truth
   *  for tab routing across multiple watchers). */
  getStatusTabMap: () => Record<string, string>
  /** After a move lands (the page reloads its timeline, the board announces it). */
  onStatusChanged: (status: string, bud: StatusSubject) => void | Promise<void>
}

export function useBudStatusTransitions(hooks: BudStatusHooks) {
  const budStore = useBUDStore()

  // Guard dialogs
  const showNoPRWarningDialog = ref(false)
  const overrideReasonDialog = ref(false)
  const overrideReasonText = ref('')
  const pendingOverrideStatus = ref('')
  const showPendingCasesDialog = ref(false)
  const pendingCasesTarget = ref('')
  const pendingCasesList = ref<{ id: string; title: string }[]>([])
  // Closing runs the close-out (XP, SP, learning recap) and can't be
  // undone, so every path to ``closed`` asks first.
  const showCloseConfirmDialog = ref(false)

  // A stage change is in flight. Further requests are ignored until it
  // settles, so a double click can't fire two PATCHes or two guards.
  const changingStatus = ref(false)
  // The BUD the change in flight is about, taken once when it starts: on
  // the board, another drop changes what getBud returns while this one is
  // still checking or waiting in a dialog.
  let subject: StatusSubject | null = null

  async function inFlight(run: () => Promise<void>): Promise<void> {
    if (changingStatus.value) return
    changingStatus.value = true
    try {
      await run()
    } finally {
      changingStatus.value = false
    }
  }

  // Backend rejection surface
  const statusErrorSnackbar = ref(false)
  const statusErrorMessage = ref('')

  // Transient info surface — used for non-error confirmations like
  // "Cancelled". Auto-dismisses via the snackbar's :timeout so users
  // see the result briefly without having to click Dismiss.
  const statusInfoSnackbar = ref(false)
  const statusInfoMessage = ref('')

  // Cancel agent task running in this phase
  const cancellingAgent = ref(false)
  // Per-design cancel state — tracks which design row is mid-cancel
  // so the matching banner can show a spinner without affecting the
  // others. ``null`` when no cancel is in flight.
  const cancellingDesignId = ref<string | null>(null)

  async function cancelRunningAgent(): Promise<void> {
    const bud = hooks.getBud()
    const taskId = bud?.active_agent_task?.id
    if (!taskId || !bud) return
    cancellingAgent.value = true
    try {
      await budStore.cancelAgentTask(bud.id, taskId)
      if (budStore.error) {
        statusErrorMessage.value = budStore.error
        statusErrorSnackbar.value = true
      } else {
        statusInfoMessage.value = 'Cancelled'
        statusInfoSnackbar.value = true
      }
    } finally {
      cancellingAgent.value = false
    }
  }

  async function cancelDesign(designId: string): Promise<void> {
    const bud = hooks.getBud()
    if (!bud) return
    cancellingDesignId.value = designId
    try {
      await budStore.cancelDesign(bud.id, designId)
      if (budStore.error) {
        statusErrorMessage.value = budStore.error
        statusErrorSnackbar.value = true
      } else {
        statusInfoMessage.value = 'Cancelled'
        statusInfoSnackbar.value = true
      }
    } finally {
      cancellingDesignId.value = null
    }
  }

  const dialogOpen = () =>
    showNoPRWarningDialog.value || overrideReasonDialog.value
    || showPendingCasesDialog.value || showCloseConfirmDialog.value
  /** A change is being checked, sent, or waiting on one of its dialogs: a new one is ignored. */
  const busy = computed(() => changingStatus.value || dialogOpen())

  function updateStatus(newStatus: string): Promise<void> {
    // Its dialog's confirm moves ``subject``, so a new change can't replace it meanwhile.
    if (dialogOpen()) return Promise.resolve()
    return inFlight(() => {
      subject = hooks.getBud()
      return runStatusGuards(newStatus)
    })
  }

  async function runStatusGuards(newStatus: string): Promise<void> {
    const bud = subject
    if (!bud) return

    if (newStatus === 'closed') {
      showCloseConfirmDialog.value = true
      return
    }

    // Intercept code_review transition: warn if no PRs are open.
    if (newStatus === 'code_review') {
      const { repos } = await budStore.fetchCodeReviewStatus(bud.id)
      const hasOpenPR = repos.some(r => r.pr_state === 'open')
      if (!hasOpenPR) {
        showNoPRWarningDialog.value = true
        return
      }
    }

    // Manual advance code_review → testing:
    //   - If every impacted repo already has a merged PR, there's nothing to
    //     "override" — the code is approved on GitHub and we just advance
    //     straight through, same outcome as the webhook auto-transition.
    //   - Otherwise the user is bypassing PR merges (e.g. docs-only change
    //     or unusual workflow), so we still prompt for a reason so the
    //     bypass is recorded on the timeline.
    if (bud.status === 'code_review' && newStatus === 'testing') {
      const { repos } = await budStore.fetchCodeReviewStatus(bud.id)
      const allMerged = repos.length > 0
        && repos.every(r => r.pr_state === 'merged')
      if (!allMerged) {
        pendingOverrideStatus.value = newStatus
        overrideReasonText.value = ''
        overrideReasonDialog.value = true
        return
      }
    }

    // Guard: testing → uat (or → prod when UAT is disabled) must have
    // every manual test case in a terminal state. Preempt the backend
    // guard client-side so the user sees the list of blocking cases in
    // a modal instead of hitting a 400 and seeing a snackbar. The
    // backend guard still fires as the authoritative check.
    //
    // Re-fetch the BUD first so qa_manual_cases reflects results saved
    // in the QA tab. The test runner composable (useQATestCases)
    // updates its own local ref but doesn't refresh the store's
    // currentBUD, so bud.qa_manual_cases can be stale after marking
    // cases as pass. It shows a result before saving it, so wait for
    // saves still in flight, or a case marked just now reads as pending.
    if (bud.status === 'testing' && (newStatus === 'uat' || newStatus === 'prod')) {
      await resultSavesSettled(bud.id)
      // Background refresh: still on this BUD by the time we got here
      // (the dialog is a child of BUDDetail) — but use the guarded
      // variant so a parallel navigation doesn't race the refresh.
      const refreshed = await hooks.refreshBud(bud.id)
      const pending = (refreshed?.qa_manual_cases ?? []).filter(
        tc => tc.result === 'pending',
      )
      if (pending.length > 0) {
        pendingCasesTarget.value = newStatus
        pendingCasesList.value = pending.map(tc => ({ id: tc.id, title: tc.title }))
        showPendingCasesDialog.value = true
        return
      }
    }

    await executeStatusChange(newStatus)
  }

  function openQATab(): void {
    showPendingCasesDialog.value = false
    if (subject) hooks.setActiveTab('testing', subject)
  }

  async function confirmNoPRWarning(): Promise<void> {
    showNoPRWarningDialog.value = false
    await inFlight(() => executeStatusChange('code_review'))
  }

  async function confirmOverrideStatus(): Promise<void> {
    const reason = overrideReasonText.value.trim()
    if (!reason) return
    overrideReasonDialog.value = false
    await inFlight(() => executeStatusChange(pendingOverrideStatus.value, reason))
  }

  async function confirmClose(): Promise<void> {
    showCloseConfirmDialog.value = false
    await inFlight(() => executeStatusChange('closed'))
  }

  async function executeStatusChange(newStatus: string, reason?: string): Promise<void> {
    const bud = subject
    if (!bud) return
    const payload: Record<string, unknown> = { status: newStatus }
    if (reason) payload.status_override_reason = reason
    const result = await budStore.updateBUD(bud.id, payload as never)
    // When the store returns null, the backend rejected the PATCH.
    // The store has already captured the detail string into
    // budStore.error via extractApiError — surface it in the
    // snackbar so the user sees exactly why (e.g. the backend
    // manual-cases guard catching a race the client-side preempt
    // missed).
    if (result === null && budStore.error) {
      statusErrorMessage.value = budStore.error
      statusErrorSnackbar.value = true
      return
    }

    // Switch tab to match the new status phase.
    const targetTab = hooks.getStatusTabMap()[newStatus]
    if (targetTab) hooks.setActiveTab(targetTab, bud)

    // The design-phase auto-trigger lives in BUDDesignPanel.vue as a
    // watcher on ``budStore.designAvailableFor`` (with ``immediate: true``)
    // — placing it there removes the parent→child ref-call mount-order
    // race we hit when the user flips status before the panel mounts.

    await hooks.onStatusChanged(newStatus, bud)
  }

  return {
    cancellingAgent,
    cancellingDesignId,
    changingStatus,
    busy,
    showCloseConfirmDialog,
    // guard-dialog state
    showNoPRWarningDialog,
    overrideReasonDialog,
    overrideReasonText,
    showPendingCasesDialog,
    pendingCasesTarget,
    pendingCasesList,
    // snackbar state
    statusErrorSnackbar,
    statusErrorMessage,
    statusInfoSnackbar,
    statusInfoMessage,
    // actions
    cancelRunningAgent,
    cancelDesign,
    updateStatus,
    openQATab,
    confirmNoPRWarning,
    confirmOverrideStatus,
    confirmClose,
  }
}
