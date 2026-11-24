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
 * An appraisal from both sides, in manual mode: HR sets the goals date and
 * opens the cycle, the manager sets goals on a first visit, the employee
 * checks in and sends, the manager sends notes, HR opens the review, the
 * employee scores, the manager agrees with one goal, changes another and
 * flags a concern, the fairness check holds the result back until HR finds
 * it fair, HR shares, and the employee reads the reason and acknowledges.
 */
import type { Api } from '../fixtures/api.ts'
import type { StackClient } from '../fixtures/client.ts'
import { expect, test } from '../fixtures/test.ts'
import type { Page } from '@playwright/test'
import { daysFromNow, lastQuarter, longDate, pick, plusDays } from '../screens/appraisals.ts'

function team(stack: StackClient) {
  return stack.seedOrg({
    members: [
      { key: 'mgr', role: 'manager', name: 'Maya Manager' },
      { key: 'emp', role: 'developer', name: 'Eli Employee', manager: 'mgr' },
      { key: 'hr', role: 'hr', name: 'Hana People' },
    ],
  })
}

/** Last quarter's draft cycle, with review dates ahead so the real hourly tick can't move it on mid-test. */
async function draftLastQuarter(hr: Api): Promise<{ id: string, name: string }> {
  const cycle = await hr.post<{ id: string, name: string }>('appraisals/cycles', { period_start: lastQuarter().start, ai_drafting: false })
  await hr.patch(`appraisals/cycles/${cycle.id}`, {
    self_due: daysFromNow(30),
    manager_due: daysFromNow(40),
    ack_due: daysFromNow(60),
  })
  return cycle
}

/** HR sets the goals date in step 1 and opens the cycle. */
async function openWithGoalsDate(hr: Page, cycle: { id: string, name: string }, goalsDue: string): Promise<void> {
  await hr.goto(`/appraisals/cycles/${cycle.id}`)
  await hr.getByLabel('Goals agreed by').fill(goalsDue)
  await hr.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(hr.getByText('Saved.')).toBeVisible()
  await hr.getByRole('button', { name: `Open ${cycle.name}` }).click()
  await expect(hr.getByText(/^Opened\. 1 person enrolled/)).toBeVisible()
}

test('a manual review from goals to the read result', async ({ signedIn, stack }) => {
  const org = await team(stack)
  const cycle = await draftLastQuarter(await stack.api(org.members.hr))
  const cycleId = cycle.id
  const goalsDue = plusDays(lastQuarter().start, 14)
  const hr = await signedIn(org.members.hr)
  await openWithGoalsDate(hr, cycle, goalsDue)

  // The quarter is over, so opening it today gives everyone the same two weeks from now.
  const ownGoalsDue = daysFromNow(14)
  const manager = await signedIn(org.members.mgr)
  await manager.goto('/appraisals/team')
  await expect(manager.getByText(`Due ${longDate(ownGoalsDue)} · 0 of 1 done`)).toBeVisible()
  await manager.getByRole('link', { name: 'Set goals for Eli Employee' }).click()
  await expect(manager.getByText(`Set goals by ${longDate(ownGoalsDue)}`)).toBeVisible()
  for (const title of ['Ship refunds', 'Automate UAT']) {
    await manager.getByLabel('Goal', { exact: true }).fill(title)
    await manager.getByLabel('How we\'ll know').fill('Live by quarter end')
    await manager.getByLabel('Why this, why now (Eli reads this)').fill('This quarter')
    await manager.getByRole('button', { name: 'Add goal' }).click()
    await expect(manager.getByRole('heading', { name: title })).toBeVisible()
  }

  // The day after the quarter ends: the last month's check-in opens.
  await stack.runAppraisalTick(org.id, lastQuarter().tickAt)

  const employee = await signedIn(org.members.emp)
  await employee.goto('/appraisals')
  // The guide opens only when asked, fits the screen without scrolling, and closes.
  await employee.getByRole('button', { name: 'How appraisals work' }).click()
  const guide = employee.getByRole('dialog', { name: 'How appraisals work' })
  await expect(guide.getByText('Each quarter')).toBeVisible()
  const box = await guide.boundingBox()
  expect(box && box.height).toBeLessThanOrEqual(employee.viewportSize()!.height)
  expect(await guide.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true)
  await guide.getByRole('button', { name: 'Got it' }).click()
  await expect(guide).toBeHidden()
  await employee.getByRole('link', { name: 'Start check-in' }).first().click()
  await employee.getByLabel('Where it stands: Ship refunds').fill('Refunds live for card payments')
  await employee.getByLabel('Anything we missed?').fill('Ran the daily suite; caught 3 regressions')
  await employee.getByLabel(/^Focus for /).fill('Nightly UAT runs')
  await employee.getByRole('button', { name: 'Send to Maya' }).click()
  await expect(employee.getByRole('button', { name: 'Send to Maya' })).toBeHidden()

  await manager.goto('/appraisals/team')
  await manager.getByRole('link', { name: 'Write notes' }).click()
  await expect(manager.getByText('Ran the daily suite; caught 3 regressions')).toBeVisible()
  await manager.getByLabel('Keep doing').fill('Catching regressions before UAT')
  await manager.getByLabel('Try next').fill('Pair on the refunds tests')
  await manager.getByRole('button', { name: 'Send to Eli' }).click()
  await expect(manager.getByText('Sent. Eli can read it now.')).toBeVisible()
  await employee.reload()
  await expect(employee.getByText('Catching regressions before UAT')).toBeVisible()

  await hr.goto(`/appraisals/cycles/${cycleId}`)
  await hr.getByRole('button', { name: 'Start the review' }).click()
  await expect(hr.getByText('Review opened for 1 person.')).toBeVisible()

  await employee.goto('/appraisals/review')
  await pick(employee, 'Result for Ship refunds', 'Achieved')
  await pick(employee, 'Result for Automate UAT', 'Partly')
  await employee.getByRole('group', { name: 'Overall rating' }).getByText('Met every time', { exact: true }).click()
  await employee.getByRole('button', { name: 'Send to Maya' }).click()
  await expect(employee.getByText('Waiting for Maya Manager.')).toBeVisible()

  await manager.goto('/appraisals/team')
  await manager.getByRole('link', { name: 'Start review' }).click()
  await pick(manager, 'Agree or change Automate UAT', 'Change')
  await pick(manager, 'Your result for Automate UAT', 'Not yet')
  await manager.getByLabel('Why, Automate UAT (Eli reads this)').fill('The suite is not running yet')
  await manager.getByLabel('Your words for Eli').fill('A steady quarter; the suite comes next')
  await pick(manager, 'Performance concern', 'Yes')
  await manager.getByLabel('What concerns you').fill('Delivery dates slip')
  await manager.getByRole('button', { name: 'Send to HR' }).click()
  await expect(manager.getByText('Eli picked the same. Maya agreed.')).toBeVisible()

  // A flagged concern holds the result back until HR finds it fair.
  await hr.goto(`/appraisals/cycles/${cycleId}/fairness`)
  await expect(hr.getByText('Nothing ready to share yet')).toBeVisible()
  await expect(hr.getByText('1 flagged result waits until you mark it fair.', { exact: false })).toBeVisible()
  await hr.getByRole('button', { name: 'Looks fair' }).click()
  await expect(hr.getByText('Marked fair: 1 result can now be shared.')).toBeVisible()
  await expect(hr.getByText(/^Looks fair · Hana People,/)).toBeVisible()
  await hr.getByRole('button', { name: 'Share 1 result' }).click()
  const confirm = hr.getByRole('dialog', { name: 'Share 1 result?' })
  await expect(confirm.getByText("Sharing can't be undone.", { exact: false })).toBeVisible()
  await confirm.getByRole('button', { name: 'Share 1 result' }).click()
  await expect(hr.getByText('Shared 1 result.')).toBeVisible()

  await employee.goto('/appraisals/review')
  await expect(employee.getByText('Changed to Not yet')).toBeVisible()
  await expect(employee.getByText('“The suite is not running yet”')).toBeVisible()
  await employee.getByLabel('Your reply').fill('Fair')
  await employee.getByRole('button', { name: "I've read this" }).click()
  await expect(employee.getByText(/You read this on .*, replying: “Fair”/)).toBeVisible()
})
