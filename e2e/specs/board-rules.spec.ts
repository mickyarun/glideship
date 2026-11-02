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
 * A stage's entry rules: a card that lacks what a stage needs can't go in,
 * by drag or by menu, and says why; Done asks before taking a card with
 * open checklist lines.
 */
import { expect, test } from '../fixtures/test.ts'
import { addCard, addChecklistItem, createBoard, requireFields, updateCard } from '../fixtures/boards.ts'
import { boardToast, cardLink, dragCard, moveFromMenu, openCardMenu, stageColumn } from '../screens/boards.ts'

test('a stage that needs an assignee refuses a card without one, by drag and by menu', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const board = await createBoard(api, 'content-seo', 'Blog')
  await requireFields(api, board, 'Writing', ['assignee'])
  const card = await addCard(api, board, 'Remote rituals explainer', 'To do')
  const page = await signedIn(org.members.pm)
  await page.goto(`/boards/${board.key}`)

  // While it's dragged, Writing says what it needs and takes no drop.
  await dragCard(page, cardLink(page, 'Remote rituals explainer'), stageColumn(page, 'Writing'), async () => {
    await expect(stageColumn(page, 'Writing')).toContainText('Needs an assignee')
  })
  await expect(boardToast(page)).toContainText('Writing needs an assignee first.')
  await expect(cardLink(stageColumn(page, 'To do'), 'Remote rituals explainer')).toBeVisible()

  // The menu marks the stage, and picking it says why too.
  const items = await openCardMenu(page, card.key)
  await expect(items.filter({ hasText: 'Writing' })).toContainText('Needs an assignee')
  await page.keyboard.press('Escape')
  await moveFromMenu(page, card.key, 'Writing')
  await expect(boardToast(page)).toContainText('Writing needs an assignee first.')
  await expect(page.getByRole('button', { name: 'Open card' })).toBeVisible()

  // Once someone is assigned, it goes in.
  await updateCard(api, board, card, { assignee_ids: [org.members.pm.id] })
  await page.reload()
  await moveFromMenu(page, card.key, 'Writing')
  await expect(cardLink(stageColumn(page, 'Writing'), 'Remote rituals explainer')).toBeVisible()
})

test('Done asks before taking a card with open checklist lines', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const board = await createBoard(api, 'blank', 'Office move')
  const card = await addCard(api, board, 'Book the movers', 'In progress')
  await addChecklistItem(api, board, card, 'Get three quotes')
  const page = await signedIn(org.members.pm)
  await page.goto(`/boards/${board.key}`)

  await moveFromMenu(page, card.key, 'Done')
  const ask = page.getByRole('dialog').filter({ hasText: 'Checklist still open' })
  await expect(ask).toContainText(`1 of 1 checklist items is still open. Move ${card.key} to Done anyway?`)
  await ask.getByRole('button', { name: 'Cancel' }).click()
  await expect(cardLink(stageColumn(page, 'In progress'), 'Book the movers')).toBeVisible()

  await moveFromMenu(page, card.key, 'Done')
  await page.getByRole('dialog').getByRole('button', { name: 'Move anyway' }).click()
  await expect(cardLink(stageColumn(page, 'Done'), 'Book the movers')).toBeVisible()
})
