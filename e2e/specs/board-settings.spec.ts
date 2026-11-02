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

/** A board admin shapes the board: stages renamed, added and given entry rules; people added. */
import { expect, test } from '../fixtures/test.ts'
import { addCard, createBoard } from '../fixtures/boards.ts'
import { cardLink, openCardMenu, stageColumn } from '../screens/boards.ts'

test('an admin renames and adds stages, and sets what one needs to enter', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'owner', role: 'org_owner' }] })
  const api = await stack.api(org.members.owner)
  const board = await createBoard(api, 'blank', 'Hiring')
  const card = await addCard(api, board, 'Senior designer role')
  const page = await signedIn(org.members.owner)
  await page.goto(`/boards/${board.key}/settings`)
  await page.getByRole('link', { name: 'Stages', exact: true }).click()

  await page.getByRole('button', { name: 'Required to enter In progress' }).click()
  await page.getByRole('option', { name: 'Assignee' }).click()
  await page.keyboard.press('Escape')
  await page.getByRole('textbox', { name: 'Name of In progress' }).fill('Interviewing')
  await page.getByRole('textbox', { name: 'New stage' }).fill('Offer')
  await page.getByRole('button', { name: 'Add stage' }).click()
  // Stages save as you go.
  await expect(page.getByText(/Saved just now/)).toBeVisible()
  await page.waitForLoadState('networkidle')

  await page.getByRole('link', { name: 'Back to the board' }).click()
  for (const stage of ['To do', 'Interviewing', 'Done', 'Offer']) await expect(stageColumn(page, stage)).toBeVisible()
  const items = await openCardMenu(page, card.key)
  await expect(items.filter({ hasText: 'Interviewing' })).toContainText('Needs an assignee')
})

test('an admin adds a person as an editor, who can then add cards', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({
    members: [{ key: 'owner', role: 'org_owner' }, { key: 'dev', role: 'developer', name: 'Dana Builder' }],
  })
  const board = await createBoard(await stack.api(org.members.owner), 'blank', 'Launch checklist', { visibility: 'members' })
  const owner = await signedIn(org.members.owner)
  await owner.goto(`/boards/${board.key}/settings`)
  await owner.getByRole('link', { name: 'Members and visibility', exact: true }).click()
  await owner.getByRole('combobox', { name: 'Add people or teams' }).fill('Dana')
  await owner.getByRole('option', { name: /Dana Builder/ }).click()
  await owner.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(owner.getByRole('listitem').filter({ hasText: 'Dana Builder' })).toBeVisible()

  const dana = await signedIn(org.members.dev)
  await dana.goto(`/boards/${board.key}`)
  const todo = stageColumn(dana, 'To do')
  await todo.getByRole('button', { name: 'Add a card' }).click()
  await todo.getByLabel('New card title').fill('Draft the announcement')
  await dana.keyboard.press('Enter')
  await expect(cardLink(todo, 'Draft the announcement')).toBeVisible()
})
