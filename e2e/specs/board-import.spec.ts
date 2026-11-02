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

/** A Trello board export becomes a team board: its lists become stages and its cards land in them. */
import { fileURLToPath } from 'node:url'
import { expect, test } from '../fixtures/test.ts'
import { boardKey } from '../fixtures/boards.ts'
import { cardLink, stageColumn } from '../screens/boards.ts'

// The same export the backend import tests read.
const EXPORT = fileURLToPath(new URL('../../backend/tests/fixtures/trello_board.json', import.meta.url))

test('an admin imports a Trello export into a new board', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'owner', role: 'org_owner' }] })
  const page = await signedIn(org.members.owner)
  await page.goto('/boards')
  await page.getByRole('link', { name: 'Import from Trello' }).or(page.getByRole('button', { name: 'Import from Trello' })).click()
  await page.getByLabel('Trello board export (.json)').setInputFiles(EXPORT)

  // Review: the board takes the export's name; lists become stages, an old one is left out.
  await expect(page.getByRole('heading', { name: 'Review the import' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Marketing launch')
  const key = boardKey()
  await page.getByRole('textbox', { name: 'Key', exact: true }).fill(key)
  await expect(page.getByRole('combobox', { name: 'What Old ideas becomes' })).toHaveValue("Don't import")
  await expect(page.getByRole('combobox', { name: 'Category for Doing' })).toHaveValue('In progress')
  await page.getByRole('button', { name: 'Import 4 cards' }).click()

  await expect(page.getByRole('heading', { name: 'Marketing launch is ready: 4 cards imported' })).toBeVisible()
  await page.getByRole('link', { name: 'Open the Marketing launch board' }).click()
  await expect(page).toHaveURL(new RegExp(`/boards/${key}$`))
  await expect(page.getByRole('heading', { level: 1, name: 'Marketing launch' })).toBeVisible()
  await expect(cardLink(stageColumn(page, 'Backlog'), 'Write the spec')).toBeVisible()
  await expect(cardLink(stageColumn(page, 'Backlog'), 'First card')).toBeVisible()
  await expect(cardLink(stageColumn(page, 'Doing'), 'In flight')).toBeVisible()
  await expect(cardLink(stageColumn(page, 'Done'), 'Done thing')).toBeVisible()
  await expect(cardLink(page, 'Ancient idea')).toHaveCount(0)
  await expect(cardLink(page, 'Shipped and archived')).toHaveCount(0)
})
