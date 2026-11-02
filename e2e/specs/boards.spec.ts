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

/** A team board from its creation: cards added, worked through the stages by menu and by drag, archived. */
import { expect, test } from '../fixtures/test.ts'
import { addCard, createBoard } from '../fixtures/boards.ts'
import { boardToast, cardLink, dragCard, moveFromMenu, stageColumn } from '../screens/boards.ts'

test('an editor makes a board from a template and adds a card', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const page = await signedIn(org.members.pm)
  await page.goto('/boards')

  await page.getByRole('button', { name: 'New board' }).click()
  const dialog = page.getByRole('dialog', { name: 'New board' })
  await dialog.getByLabel('Name').fill('Site ops')
  await dialog.getByText('Ops', { exact: true }).click()
  await dialog.getByRole('button', { name: 'Create board' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Site ops' })).toBeVisible()
  for (const stage of ['Backlog', 'To do', 'In progress', 'Waiting', 'Done']) {
    await expect(stageColumn(page, stage)).toBeVisible()
  }
  const backlog = stageColumn(page, 'Backlog')
  await backlog.getByRole('button', { name: 'Add a card' }).click()
  await backlog.getByLabel('New card title').fill('Rotate the TLS certificates')
  await page.keyboard.press('Enter')
  await expect(cardLink(backlog, 'Rotate the TLS certificates')).toBeVisible()

  // The card keeps across a reload, and its page opens from the title.
  await page.reload()
  await cardLink(stageColumn(page, 'Backlog'), 'Rotate the TLS certificates').click()
  await expect(page.getByRole('heading', { level: 1, name: 'Rotate the TLS certificates' })).toBeVisible()
})

test('a card moves through the stages from its menu and by drag', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const board = await createBoard(api, 'ops', 'Release ops')
  const card = await addCard(api, board, 'Patch the base images')
  const page = await signedIn(org.members.pm)
  await page.goto(`/boards/${board.key}`)

  await moveFromMenu(page, card.key, 'To do')
  await expect(cardLink(stageColumn(page, 'To do'), 'Patch the base images')).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: `Moved ${card.key} to To do` })).toBeAttached()

  await dragCard(page, cardLink(page, 'Patch the base images'), stageColumn(page, 'In progress'))
  await expect(cardLink(stageColumn(page, 'In progress'), 'Patch the base images')).toBeVisible()
  await expect(cardLink(stageColumn(page, 'To do'), 'Patch the base images')).toHaveCount(0)

  // Where it landed is kept.
  await page.reload()
  await expect(cardLink(stageColumn(page, 'In progress'), 'Patch the base images')).toBeVisible()
})

test('archiving a card offers Undo, and the archived view restores it too', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const board = await createBoard(api, 'blank', 'Errands')
  const card = await addCard(api, board, 'Order standing desks')
  const page = await signedIn(org.members.pm)
  await page.goto(`/boards/${board.key}`)

  const archive = async () => {
    await page.getByRole('button', { name: `Actions for ${card.key}`, exact: true }).click()
    await page.locator('.v-overlay--active .v-list-item').filter({ hasText: 'Archive' }).click()
  }
  await archive()
  await expect(boardToast(page)).toContainText(`Archived ${card.key}`)
  await page.getByRole('button', { name: 'Undo' }).click()
  await expect(cardLink(stageColumn(page, 'To do'), 'Order standing desks')).toBeVisible()

  await archive()
  await expect(cardLink(page, 'Order standing desks')).toHaveCount(0)
  await page.getByRole('button', { name: 'Archived', exact: true }).click()
  await page.getByRole('button', { name: `Actions for ${card.key}`, exact: true }).click()
  await page.locator('.v-overlay--active .v-list-item').filter({ hasText: 'Restore' }).click()
  await page.getByRole('button', { name: 'Archived', exact: true }).click()
  await expect(cardLink(stageColumn(page, 'To do'), 'Order standing desks')).toBeVisible()
})
