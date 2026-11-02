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
 * Handing a product card over to Delivery: a BUD is made from the card and
 * lands where the board says, the card follows its BUD, and the BUD can be
 * sent back with a reason, which brings the card back to the board.
 */
import { expect, test } from '../fixtures/test.ts'
import { addCard, createBoard, enableHandover } from '../fixtures/boards.ts'
import { openBudMenu } from '../screens/buds.ts'
import { cardLink, deliveryColumn, openCardMenu, stageColumn } from '../screens/boards.ts'

test('a PM hands a card over, the BUD lands at design, and sending it back returns the card', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const board = await createBoard(api, 'product', 'Growth')
  await enableHandover(api, board, 'design')
  const card = await addCard(api, board, 'Annual billing toggle', 'Ready for dev', {
    description_md: 'Let teams pay yearly at a discount.',
  })
  const page = await signedIn(org.members.pm)
  await page.goto(`/boards/${board.key}`)

  // From the card's menu: its page opens with the handover dialog.
  const items = await openCardMenu(page, card.key)
  await items.filter({ hasText: 'Hand over to Delivery' }).click()
  const dialog = page.getByRole('dialog', { name: `Hand over ${card.key} to Delivery` })
  await expect(dialog.getByLabel('BUD title')).toHaveValue('Annual billing toggle')
  await dialog.getByRole('radio', { name: 'Design', exact: true }).click()
  await dialog.getByRole('button', { name: 'Create BUD and hand over' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('link', { name: /BUD-001/ }).first()).toBeVisible()

  // On Delivery the BUD sits in Design and names the card it came from.
  await page.goto('/buds')
  const design = deliveryColumn(page, 'Design')
  await expect(cardLink(design, 'Annual billing toggle')).toBeVisible()
  await expect(design.getByRole('link', { name: new RegExp(card.key) })).toBeVisible()

  // Sent back with a reason: the BUD is discarded and the card returns to Ideas.
  await cardLink(design, 'Annual billing toggle').click()
  await (await openBudMenu(page)).getByRole('menuitem', { name: 'Send back to Growth…' }).click()
  const back = page.getByRole('dialog', { name: `Send BUD-001 back to ${card.key}?` })
  await back.getByLabel('Reason (required)').fill('Pricing is still being decided')
  await back.getByRole('button', { name: 'Discard BUD and send back' }).click()
  await expect(back).toBeHidden()

  await page.goto(`/boards/${board.key}`)
  await expect(cardLink(stageColumn(page, 'Ideas'), 'Annual billing toggle')).toBeVisible()
  await cardLink(stageColumn(page, 'Ideas'), 'Annual billing toggle').click()
  await expect(page.getByText('Pricing is still being decided').first()).toBeVisible()
})
