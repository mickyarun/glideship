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
 * The holiday list: one click from My leave or the team calendar shows the
 * whole year for the viewer's office, and HR can switch offices.
 */
import { expect, test } from '../fixtures/test.ts'
import { addHolidays, addPolicy, ownPolicyId } from '../fixtures/holidays.ts'
import type { StackClient } from '../fixtures/client.ts'

const YEAR = new Date().getFullYear()
// First and last day of this (calendar) leave year: one behind, one ahead.
const NEW_YEAR = { date: `${YEAR}-01-01`, name: 'New Year' }
const YEAR_END = { date: `${YEAR}-12-31`, name: 'Year end break', kind: 'optional' as const }

async function office(stack: StackClient) {
  const org = await stack.seedOrg({
    members: [
      { key: 'hr', role: 'hr', name: 'Hana People' },
      { key: 'emp', role: 'developer', name: 'Eli Employee', manager: 'hr' },
    ],
  })
  const hr = await stack.api(org.members.hr)
  await addHolidays(hr, await ownPolicyId(hr), [NEW_YEAR, YEAR_END])
  return { org, hr }
}

test('an employee opens the year of holidays from My leave and the team calendar', async ({ signedIn, stack }) => {
  const { org } = await office(stack)
  const page = await signedIn(org.members.emp)
  await page.goto('/leave')
  await page.getByRole('link', { name: 'Holidays', exact: true }).click()

  await expect(page.getByRole('heading', { name: 'Holidays', level: 1 })).toBeVisible()
  const list = page.getByRole('list', { name: 'Holidays' })
  await expect(list.getByRole('listitem')).toHaveCount(2)
  const yearEnd = list.getByRole('listitem').filter({ hasText: YEAR_END.name })
  await expect(yearEnd).toContainText('Optional')
  await expect(yearEnd).not.toHaveClass(/holiday--past/)
  // Only someone outside the year's first day sees New Year as over.
  if (new Date().getMonth() > 0 || new Date().getDate() > 1) {
    await expect(list.getByRole('listitem').filter({ hasText: NEW_YEAR.name })).toHaveClass(/holiday--past/)
  }
  // Just their own office: nothing to switch to.
  await expect(page.getByRole('radiogroup', { name: 'Office' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Next year' }).click()
  await expect(page.getByText('No holidays on the Default calendar for this leave year.')).toBeVisible()

  await page.goto('/leave/team')
  await page.getByRole('link', { name: 'Holidays', exact: true }).click()
  await expect(page.getByRole('list', { name: 'Holidays' }).getByRole('listitem')).toHaveCount(2)
})

test('HR switches between offices', async ({ signedIn, stack }) => {
  const { org, hr } = await office(stack)
  const london = await addPolicy(hr, 'London')
  await addHolidays(hr, london.id, [{ date: `${YEAR}-08-25`, name: 'Summer bank holiday' }])

  const page = await signedIn(org.members.hr)
  await page.goto('/leave/holidays')
  const offices = page.getByRole('radiogroup', { name: 'Office' })
  await offices.getByRole('radio', { name: 'London' }).click()
  const list = page.getByRole('list', { name: 'Holidays' })
  await expect(list.getByRole('listitem')).toHaveCount(1)
  await expect(list).toContainText('Summer bank holiday')
  await expect(page).toHaveURL(new RegExp(`calendar=${london.id}`))
})
