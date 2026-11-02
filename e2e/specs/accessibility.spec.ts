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
 * The main screens pass an automated WCAG 2.1 AA check (see screens/a11y.ts).
 * Each test waits for the screen's heading and for the network to settle, so
 * axe sees the screen as a person would, not a loading skeleton.
 */
import type { Page } from '@playwright/test'
import { createBud } from '../fixtures/api.ts'
import { addCard, addChecklistItem, createBoard } from '../fixtures/boards.ts'
import { expect, test } from '../fixtures/test.ts'
import { expectAccessible } from '../screens/a11y.ts'
import { openCardMenu } from '../screens/boards.ts'
import { openAccountMenu } from '../screens/shell.ts'

async function check(page: Page, path: string, heading: string | RegExp): Promise<void> {
  await page.goto(path)
  await expect(page.getByRole('heading', { name: heading }).first()).toBeVisible()
  await page.waitForLoadState('networkidle')
  await expectAccessible(page, path)
}

test('the login page', async ({ page }) => {
  await check(page, '/login', 'Sign in')
})

test('the engineering screens', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'owner', role: 'org_owner', name: 'Olu Owner' }] })
  const bud = await createBud(await stack.api(org.members.owner), 'Accessible BUD')
  const page = await signedIn(org.members.owner)
  await check(page, '/dashboard', /^Good/)
  // The account menu, open: its actions are menu items, its theme choice a radio group.
  const menu = await openAccountMenu(page, 'Olu Owner')
  await expect(menu.getByRole('menuitem', { name: 'Sign out' })).toBeVisible()
  await expect(menu.getByRole('group', { name: 'Theme' }).getByRole('menuitemradio')).toHaveCount(3)
  await expectAccessible(page, 'the account menu')
  await page.keyboard.press('Escape')
  await check(page, '/buds', 'Delivery')
  await check(page, `/buds/${bud.id}`, /Accessible BUD/)
  await check(page, '/bugs', 'Bugs')
  await check(page, '/features', 'Features')
  await check(page, '/settings', 'Settings')
  await check(page, '/members', 'Members')
  await check(page, '/settings/mcp-connect', 'Connect your local AI')
})

test('the people screens', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({
    members: [
      { key: 'hr', role: 'hr', name: 'Hana People' },
      { key: 'emp', role: 'developer', name: 'Eli Employee', manager: 'hr' },
    ],
  })
  const page = await signedIn(org.members.hr)
  await check(page, '/leave', 'My leave')
  await check(page, '/leave/approvals', 'Approvals')
  await check(page, '/leave/team', 'Team calendar')
  await check(page, '/people', 'Employees')
  await check(page, `/people/${org.members.emp.id}`, 'Eli Employee')
})

test('the board screens', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'owner', role: 'org_owner', name: 'Olu Owner' }] })
  const api = await stack.api(org.members.owner)
  const board = await createBoard(api, 'content-seo', 'Accessible content')
  const card = await addCard(api, board, 'Accessible card', 'Writing', { description_md: 'Some **notes**.' })
  await addChecklistItem(api, board, card, 'Check the headings')
  await createBud(api, 'Accessible BUD')
  const page = await signedIn(org.members.owner)

  await check(page, '/boards', 'Boards')
  await check(page, `/boards/${board.key}`, 'Accessible content')
  // A card's menu, open: its stages with their locks.
  await openCardMenu(page, card.key)
  await expectAccessible(page, 'a card menu')
  await page.keyboard.press('Escape')
  await check(page, `/boards/${board.key}/cards/${card.number}`, 'Accessible card')
  await check(page, `/boards/${board.key}/settings`, 'Board settings')
  await check(page, `/boards/${board.key}/metrics`, 'Metrics')
  await check(page, '/boards/imports/trello', 'Import from Trello')
  // Delivery's card menu too.
  await check(page, '/buds', 'Delivery')
  await openCardMenu(page, 'BUD-001')
  await expectAccessible(page, 'a Delivery card menu')
})
