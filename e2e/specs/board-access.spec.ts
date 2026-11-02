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
 * Who sees a board and what they may do there: a members-only board is
 * hidden from everyone else, a viewer reads and can't change cards, and a
 * board-only person (no engineering access) works on boards without
 * reaching Delivery.
 */
import { expect, test } from '../fixtures/test.ts'
import { addBoardMember, addCard, createBoard } from '../fixtures/boards.ts'
import { cardLink, openCardMenu, stageColumn } from '../screens/boards.ts'

test('a members-only board is hidden from someone who is not on it', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'owner', role: 'org_owner' }, { key: 'dev', role: 'developer' }] })
  const board = await createBoard(await stack.api(org.members.owner), 'ops', 'Incident review', { visibility: 'members' })
  const page = await signedIn(org.members.dev)

  await page.goto('/boards')
  await expect(page.getByRole('heading', { level: 1, name: 'Boards' })).toBeVisible()
  await expect(page.getByText('Incident review')).toHaveCount(0)

  await page.goto(`/boards/${board.key}`)
  await expect(page.getByText("This board doesn't exist, or you don't have access")).toBeVisible()
  await expect(page.getByRole('link', { name: 'Go to your boards' })).toBeVisible()
})

test('a viewer reads the board but cannot change its cards', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({
    members: [{ key: 'owner', role: 'org_owner', name: 'Olu Owner' }, { key: 'dev', role: 'developer' }],
  })
  const api = await stack.api(org.members.owner)
  const board = await createBoard(api, 'ops', 'Vendor contracts', { visibility: 'members' })
  const card = await addCard(api, board, 'Renew the CDN contract')
  await addBoardMember(api, board, org.members.dev.id, 'viewer')
  const page = await signedIn(org.members.dev)
  await page.goto(`/boards/${board.key}`)

  await expect(page.getByRole('note')).toContainText('You can view and comment on Vendor contracts. Ask Olu Owner (admin) for edit access.')
  await expect(cardLink(stageColumn(page, 'Backlog'), 'Renew the CDN contract')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add a card' })).toHaveCount(0)
  await expect(page.getByText('Drag cards between stages')).toHaveCount(0)
  const items = await openCardMenu(page, card.key)
  await expect(items).toHaveText(['Copy link'])
})

test('a board-only person works on boards and never reaches Delivery', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'owner', role: 'org_owner' }, { key: 'sales', role: 'sales' }] })
  const owner = await stack.api(org.members.owner)
  const board = await createBoard(owner, 'blank', 'Deals')
  // Everyone in the org can view an org-visible board; editing takes membership.
  await addBoardMember(owner, board, org.members.sales.id, 'editor')
  const page = await signedIn(org.members.sales)

  await page.goto('/boards')
  await expect(page.getByRole('link', { name: /^Deals/ }).first()).toBeVisible()
  await expect(page.getByRole('navigation').getByRole('link', { name: 'Delivery', exact: true })).toHaveCount(0)

  await page.goto(`/boards/${board.key}`)
  const todo = stageColumn(page, 'To do')
  await todo.getByRole('button', { name: 'Add a card' }).click()
  await todo.getByLabel('New card title').fill('Follow up with Acme')
  await page.keyboard.press('Enter')
  await expect(cardLink(todo, 'Follow up with Acme')).toBeVisible()

  await page.goto('/buds')
  await expect(page).not.toHaveURL(/\/buds$/)
})
