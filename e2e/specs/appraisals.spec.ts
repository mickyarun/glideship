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
 * An appraisal from both sides, in manual mode: a month recorded, the
 * manager's feedback, then HR opens the review, the employee scores, the
 * manager agrees with one goal and changes another, HR shares, and the
 * employee reads the reason, acknowledges and proposes next period's goal.
 */
import type { Api } from '../fixtures/api.ts'
import type { StackClient } from '../fixtures/client.ts'
import { expect, test } from '../fixtures/test.ts'
import { daysFromNow, lastQuarter, openAppraisals, pick } from '../screens/appraisals.ts'

interface Row { id: string, person_name: string }

function team(stack: StackClient) {
  return stack.seedOrg({
    members: [
      { key: 'mgr', role: 'manager', name: 'Maya Manager' },
      { key: 'emp', role: 'developer', name: 'Eli Employee', manager: 'mgr' },
      { key: 'hr', role: 'hr', name: 'Hana People' },
    ],
  })
}

/** Last quarter's cycle, opened, with its last month's check-in and feedback. */
async function lastQuarterCycle(stack: StackClient, orgId: string, hr: Api): Promise<string> {
  const quarter = lastQuarter()
  const cycle = await hr.post<{ id: string }>('appraisals/cycles', { period_start: quarter.start, ai_drafting: false })
  // Due dates ahead, so the real hourly tick can't move the review on mid-test.
  await hr.patch(`appraisals/cycles/${cycle.id}`, {
    self_due: daysFromNow(30),
    manager_due: daysFromNow(40),
    ack_due: daysFromNow(60),
  })
  await hr.post(`appraisals/cycles/${cycle.id}/activate`, {})
  await stack.runAppraisalTick(orgId, quarter.tickAt)
  return cycle.id
}

test('a manual review from check-in to growth conversation', async ({ signedIn, stack }) => {
  const org = await team(stack)
  const hrApi = await stack.api(org.members.hr)
  const mgrApi = await stack.api(org.members.mgr)
  const cycleId = await lastQuarterCycle(stack, org.id, hrApi)
  const [eli] = await mgrApi.get<Row[]>('appraisals/team')
  for (const title of ['Ship refunds', 'Automate UAT']) {
    await mgrApi.post(`appraisals/${eli.id}/goals`, { title, reason: 'This quarter' })
  }

  const employee = await signedIn(org.members.emp)
  await openAppraisals(employee, '/appraisals')
  await employee.getByRole('button', { name: 'Add a line' }).first().click()
  await employee.getByLabel('Delivery & quality, line 1').fill('Ran the daily suite; caught 3 regressions')
  await employee.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(employee.getByRole('button', { name: 'Save', exact: true })).toBeDisabled()

  const manager = await signedIn(org.members.mgr)
  await openAppraisals(manager, '/appraisals/team')
  await manager.getByRole('link', { name: 'Write feedback' }).click()
  await manager.getByLabel('Keep doing').fill('Catching regressions before UAT')
  await manager.getByLabel('Try next').fill('Pair on the refunds tests')
  await manager.getByRole('button', { name: 'Mark done' }).click()
  await expect(manager.getByText('Marked done.')).toBeVisible()
  await employee.reload()
  await expect(employee.getByText('Keep: Catching regressions before UAT')).toBeVisible()

  const hr = await signedIn(org.members.hr)
  await openAppraisals(hr, `/appraisals/cycles/${cycleId}`)
  await hr.getByRole('button', { name: 'Start the review' }).click()
  await expect(hr.getByText('Review opened for 1 person.')).toBeVisible()

  await employee.goto('/appraisals/review')
  await pick(employee, 'Result for Ship refunds', 'Achieved')
  await pick(employee, 'Result for Automate UAT', 'Partly')
  await pick(employee, 'Overall band', 'Meets always (3)')
  await employee.getByRole('button', { name: 'Submit to Maya Manager' }).click()
  await expect(employee.getByText('Waiting for Maya Manager.')).toBeVisible()

  await manager.goto(`/appraisals/reviews/${eli.id}`)
  await pick(manager, 'Agree or change Automate UAT', 'Change')
  await pick(manager, 'Result', 'Not yet')
  await manager.getByLabel('Reason (they read this)').fill('The suite is not running yet')
  await manager.getByRole('button', { name: 'Submit to HR' }).click()
  await expect(manager.getByText('Final band: Meets always (3)')).toBeVisible()

  await hr.reload()
  await hr.getByRole('button', { name: 'Share all ready results' }).click()
  await expect(hr.getByText('Shared 1 result.')).toBeVisible()

  await employee.reload()
  await expect(employee.getByText('you said Partly; The suite is not running yet')).toBeVisible()
  await employee.getByLabel('Your reply (optional; HR reads it too)').fill('Fair')
  await employee.getByRole('button', { name: 'Acknowledge' }).click()
  await expect(employee.getByText('Acknowledged: “Fair”')).toBeVisible()
  await employee.getByRole('button', { name: 'Add a goal for next period' }).click()
  await employee.getByLabel('Goal', { exact: true }).fill('Run the UAT suite nightly')
  await employee.getByRole('button', { name: 'Add goal' }).click()
  await expect(employee.getByText('Proposed by Eli Employee')).toBeVisible()
})
