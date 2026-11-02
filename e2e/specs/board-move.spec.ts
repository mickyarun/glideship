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

/** A card moves to another board, keeps its history there, and its old link still finds it. */
import { expect, test } from '../fixtures/test.ts'
import { addCard, addChecklistItem, createBoard } from '../fixtures/boards.ts'
import { pickOption } from '../screens/forms.ts'
import { boardToast, cardLink, openCardMenu, stageColumn } from '../screens/boards.ts'

test('a card moves to another board and its old key still opens it', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const from = await createBoard(api, 'ops', 'Support desk')
  const to = await createBoard(api, 'blank', 'Platform')
  const card = await addCard(api, from, 'Rate limit the webhook endpoint')
  await addChecklistItem(api, from, card, 'Pick the limit')
  const page = await signedIn(org.members.pm)
  await page.goto(`/boards/${from.key}`)

  const items = await openCardMenu(page, card.key)
  await items.filter({ hasText: 'Move to another board' }).click()
  const dialog = page.getByRole('dialog', { name: `Move ${card.key} to another board` })
  await expect(dialog).toContainText('It keeps its comments, checklist, files and history.')
  await pickOption(dialog, 'Board', /^Platform/)
  await pickOption(dialog, 'Stage', 'In progress')
  await dialog.getByRole('button', { name: 'Move', exact: true }).click()

  await expect(boardToast(page)).toContainText(`${card.key} moved to Platform as ${to.key}-1`)
  await expect(cardLink(page, 'Rate limit the webhook endpoint')).toHaveCount(0)

  await page.goto(`/boards/${to.key}`)
  await expect(cardLink(stageColumn(page, 'In progress'), 'Rate limit the webhook endpoint')).toBeVisible()

  // The old key redirects to the card where it is now, checklist and all.
  await page.goto(`/boards/${from.key}/cards/${card.number}`)
  await expect(page).toHaveURL(new RegExp(`/boards/${to.key}/cards/1$`))
  await expect(page.getByRole('heading', { level: 1, name: 'Rate limit the webhook endpoint' })).toBeVisible()
  await expect(page.getByText('Pick the limit')).toBeVisible()
})
