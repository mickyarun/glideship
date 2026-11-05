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
 * Leave on a day already booked as work from home: it can be asked for, it
 * replaces the WFH that day, and the day is counted once. WFH can't go on a
 * day that is already leave.
 */
import { readFileSync } from 'node:fs'
import type { Locator } from '@playwright/test'
import { approveLeave, requestLeave, requestWfh } from '../fixtures/api.ts'
import type { StackClient } from '../fixtures/client.ts'
import { type LeaveDays, upcomingWeekdays } from '../fixtures/dates.ts'
import { expect, test } from '../fixtures/test.ts'
import { dayLabel, onlyThoseDays, openApproval, sendLeaveRequest, showCalendarMonth } from '../screens/leave.ts'

function team(stack: StackClient) {
  return stack.seedOrg({
    members: [
      { key: 'hr', role: 'hr', name: 'Hana People' },
      { key: 'mgr', role: 'manager', name: 'Maya Manager' },
      { key: 'emp', role: 'developer', name: 'Eli Employee', manager: 'mgr' },
      { key: 'peer', role: 'developer', name: 'Pia Peer', manager: 'mgr' },
    ],
  })
}

type Org = Awaited<ReturnType<typeof team>>

/** The first of the two days alone: both are booked as WFH, this one goes on leave. */
const firstDay = (days: LeaveDays): LeaveDays => ({ ...days, to: days.from })

/** Eli's approved WFH across both days. */
async function wfhBooked(stack: StackClient, org: Org, days: LeaveDays): Promise<void> {
  const wfh = await requestWfh(await stack.api(org.members.emp), days, 'Boiler repair')
  await approveLeave(await stack.api(org.members.mgr), wfh.id)
}

/** Eli's approved leave on the first of those days. */
async function leaveTaken(stack: StackClient, org: Org, days: LeaveDays): Promise<void> {
  const leave = await requestLeave(await stack.api(org.members.emp), org.leaveTypes.CL, firstDay(days), 'Unwell')
  await approveLeave(await stack.api(org.members.mgr), leave.id)
}

/** The text under a column of the summary, for one person's row. */
async function cellUnder(summary: Locator, column: string, name: string): Promise<Locator> {
  const headers = (await summary.getByRole('columnheader').allTextContents()).map(h => h.trim())
  return summary.getByRole('row').filter({ hasText: name }).getByRole('cell').nth(headers.indexOf(column))
}

test('an employee on WFH asks for leave on one of those days', async ({ signedIn, stack }) => {
  const org = await team(stack)
  const days = upcomingWeekdays()
  await wfhBooked(stack, org, days)

  const employee = await signedIn(org.members.emp)
  await employee.goto('/leave')
  await sendLeaveRequest(employee, 'Casual leave', firstDay(days), 'Eye pain, going to hospital')

  const manager = await signedIn(org.members.mgr)
  await openApproval(manager, 'Eli Employee')
  await manager.getByRole('button', { name: 'Approve' }).click()
  await manager.goto('/leave/team')
  const month = await showCalendarMonth(manager, days.start)
  const leaveDay = month.getByRole('button', { name: `${dayLabel(days.start)}, 1 out` })
  await expect(leaveDay).toContainText('Eli Em')
  await expect(leaveDay.getByTitle(/Work from home/)).toHaveCount(0)
  const nextDay = new Date(days.start)
  nextDay.setDate(nextDay.getDate() + 1)
  await expect(month.getByRole('button', { name: `${dayLabel(nextDay)}, 1 out` }).getByTitle(/Work from home/)).toBeVisible()
})

test('the report counts a WFH day taken over by leave once', async ({ signedIn, stack }) => {
  const org = await team(stack)
  const days = upcomingWeekdays()
  await wfhBooked(stack, org, days)
  await leaveTaken(stack, org, days)

  const page = await signedIn(org.members.hr)
  await page.goto('/leave/reports')
  await onlyThoseDays(page, days)
  const summary = page.getByRole('region', { name: 'Leave taken by person' })
  await expect(summary.getByText('Eli Employee')).toBeVisible()
  await expect(await cellUnder(summary, 'WFH', 'Eli Employee')).toHaveText('1')

  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const [header, ...rows] = readFileSync(await (await download).path(), 'utf8').trim().split(/\r?\n/)
  const eli = rows.find(row => row.includes('Eli Employee'))?.split(',') ?? []
  expect(Number(eli[header.split(',').indexOf('WFH days')])).toBe(1)
})

test('WFH cannot go on a day that is already leave', async ({ signedIn, stack }) => {
  const org = await team(stack)
  const days = upcomingWeekdays()
  await leaveTaken(stack, org, days)

  const employee = await signedIn(org.members.emp)
  await employee.goto('/leave')
  await employee.getByRole('button', { name: 'Work from home' }).click()
  await employee.getByLabel('From', { exact: true }).fill(days.from)
  await employee.getByLabel('To', { exact: true }).fill(days.from)
  await expect(employee.getByText(/You already have an approved request covering/)).toBeVisible()
  await expect(employee.getByRole('button', { name: 'Send request' })).toBeDisabled()
})

test('the approver can tell WFH from leave under "Also out"', async ({ signedIn, stack }) => {
  const org = await team(stack)
  const days = upcomingWeekdays()
  await wfhBooked(stack, org, days)
  await requestLeave(await stack.api(org.members.peer), org.leaveTypes.CL, days, 'Family wedding')

  const manager = await signedIn(org.members.mgr)
  await openApproval(manager, 'Pia Peer')
  await expect(manager.getByText(/Eli \(WFH, /)).toBeVisible()
})
