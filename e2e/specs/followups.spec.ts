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

/** Turning on the daily follow-ups DM and picking when it arrives. */
import type { Page } from '@playwright/test'
import { expect, test } from '../fixtures/test.ts'

function savedSchedule(page: Page) {
  return page.waitForResponse((r) => r.url().endsWith('/api/v1/me/followups') && r.request().method() === 'PUT')
}

test('the daily follow-ups start off, and a schedule set on the page is kept', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'dev', role: 'developer' }] })
  const page = await signedIn(org.members.dev)
  await page.goto('/profile/notifications')
  const followups = page.getByRole('checkbox', { name: 'Daily follow-ups' })
  await expect(followups).not.toBeChecked()
  await expect(page.getByLabel('Send at')).toHaveCount(0)

  let saved = savedSchedule(page)
  await followups.check()
  expect((await saved).ok()).toBe(true)

  const sendAt = page.getByLabel('Send at')
  saved = savedSchedule(page)
  await sendAt.fill('07:30')
  await sendAt.blur()
  expect((await saved).ok()).toBe(true)

  saved = savedSchedule(page)
  await page.getByRole('radio', { name: 'Every day' }).click()
  expect((await saved).ok()).toBe(true)

  await page.reload()
  await expect(followups).toBeChecked()
  await expect(page.getByLabel('Send at')).toHaveValue('07:30')
  await expect(page.getByRole('radio', { name: 'Every day' })).toHaveAttribute('aria-checked', 'true')
  // Its switch lives on its own card, not again in the list below.
  await expect(page.getByRole('checkbox', { name: 'Daily follow-ups' })).toHaveCount(1)
})
