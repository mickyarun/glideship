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
 * Moving BUDs on the Delivery board, by drag and from a card's ⋯ menu: one
 * stage at a time, each stage saying what it needs, closing behind a
 * confirm, and QA taking BUDs only out of testing.
 */
import { createBud, moveBud } from '../fixtures/api.ts'
import { expect, test } from '../fixtures/test.ts'
import { boardToast, cardLink, deliveryColumn, dragCard, moveFromMenu, openCardMenu } from '../screens/boards.ts'

const PRD = '## Problem\nInvoices are emailed by hand.'

test('a BUD drags one stage at a time, and a stage it cannot enter yet says why', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  await createBud(api, 'Bare idea')
  await createBud(api, 'Invoice emails', { requirements_md: PRD })
  const page = await signedIn(org.members.pm)
  await page.goto('/buds')
  await page.getByRole('button', { name: 'Discarded' }).click()

  // No PRD: Design says so while the BUD is held over it, and the drop is refused.
  await dragCard(page, cardLink(page, 'Bare idea'), deliveryColumn(page, 'Design'), async () => {
    await expect(deliveryColumn(page, 'Design')).toContainText('Needs a PRD')
    await expect(deliveryColumn(page, 'Development')).toContainText('One stage at a time')
    await expect(deliveryColumn(page, 'Discarded')).toContainText('Discard from the BUD page')
  })
  await expect(boardToast(page)).toContainText('Design needs a PRD first.')
  await page.getByRole('button', { name: 'Open BUD' }).click()
  const toDesign = page.getByRole('button', { name: 'Move to Design' })
  await expect(toDesign).toBeDisabled()
  await expect(toDesign).toHaveAccessibleDescription('Design needs a PRD first.')

  // With a PRD it goes in, and stays there.
  await page.goto('/buds')
  await dragCard(page, cardLink(page, 'Invoice emails'), deliveryColumn(page, 'Design'))
  await expect(cardLink(deliveryColumn(page, 'Design'), 'Invoice emails')).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'Moved BUD-002 to Design' })).toBeAttached()
  await page.reload()
  await expect(cardLink(deliveryColumn(page, 'Design'), 'Invoice emails')).toBeVisible()

  // Two stages on is refused, with the BUD page as the way there.
  await dragCard(page, cardLink(page, 'Invoice emails'), deliveryColumn(page, 'Development'))
  await expect(boardToast(page)).toContainText('BUD-002 moves one stage at a time. Open it to move it to Development.')
  await expect(cardLink(deliveryColumn(page, 'Design'), 'Invoice emails')).toBeVisible()
})

test('the card menu moves a BUD from the keyboard, and closing asks first', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }] })
  const api = await stack.api(org.members.pm)
  const bud = await createBud(api, 'Usage export', { requirements_md: PRD })
  await moveBud(api, bud.id, 'prod')
  const page = await signedIn(org.members.pm)
  await page.goto('/buds')

  const items = await openCardMenu(page, 'BUD-001')
  await expect(items.filter({ hasText: 'Prod (current)' })).toHaveClass(/v-list-item--disabled/)
  await expect(items.filter({ hasText: 'Testing' })).toContainText('One stage at a time')
  await page.keyboard.press('Escape')

  await moveFromMenu(page, 'BUD-001', 'UAT')
  await expect(cardLink(deliveryColumn(page, 'UAT'), 'Usage export')).toBeFocused()
  await moveFromMenu(page, 'BUD-001', 'Prod')
  await expect(cardLink(deliveryColumn(page, 'Prod'), 'Usage export')).toBeVisible()

  await moveFromMenu(page, 'BUD-001', 'Closed')
  const close = page.getByRole('dialog', { name: 'Close this BUD?' })
  await close.getByRole('button', { name: 'Cancel' }).click()
  await expect(cardLink(deliveryColumn(page, 'Prod'), 'Usage export')).toBeVisible()
  await moveFromMenu(page, 'BUD-001', 'Closed')
  await page.getByRole('dialog', { name: 'Close this BUD?' }).getByRole('button', { name: 'Close BUD' }).click()
  await expect(cardLink(deliveryColumn(page, 'Closed'), 'Usage export')).toBeVisible()

  // A closed BUD stays put: its menu has Copy link only.
  await expect(await openCardMenu(page, 'BUD-001')).toHaveText(['Copy link'])
})

test('QA takes a BUD out of testing, and nowhere else', async ({ signedIn, stack }) => {
  const org = await stack.seedOrg({ members: [{ key: 'pm', role: 'pm' }, { key: 'qa', role: 'qa' }] })
  const pmApi = await stack.api(org.members.pm)
  const bud = await createBud(pmApi, 'Audit log filters', { requirements_md: PRD })
  await moveBud(pmApi, bud.id, 'testing', 'Reviewed on the call')
  const page = await signedIn(org.members.qa)
  await page.goto('/buds')

  const items = await openCardMenu(page, 'BUD-001')
  await expect(items.filter({ hasText: 'Code Review' })).toContainText('Only out of Testing')
  await page.keyboard.press('Escape')
  await moveFromMenu(page, 'BUD-001', 'Code Review')
  await expect(boardToast(page)).toContainText('You can only move BUDs out of Testing.')

  await dragCard(page, cardLink(page, 'Audit log filters'), deliveryColumn(page, 'UAT'))
  await expect(cardLink(deliveryColumn(page, 'UAT'), 'Audit log filters')).toBeVisible()
})
