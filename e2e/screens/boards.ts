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

/** Team boards and the Delivery board: columns, cards, their menus, and dragging. */
import { expect, type Locator, type Page } from '@playwright/test'

/** A team board's stage column, named "<stage>, <category>". */
export function stageColumn(page: Page, stage: string): Locator {
  return page.getByRole('region', { name: new RegExp(`^${stage}, `) })
}

/** A Delivery board column, named "<stage>, <n> BUD(s)". */
export function deliveryColumn(page: Page, stage: string): Locator {
  return page.getByRole('region', { name: new RegExp(`^${stage}, \\d+ BUDs?$`) })
}

/** A card on any board, by its title link. */
export function cardLink(scope: Page | Locator, title: string): Locator {
  return scope.getByRole('link', { name: title, exact: true })
}

/** Opens a card's ⋯ menu from the keyboard and returns its items. */
export async function openCardMenu(page: Page, cardRef: string): Promise<Locator> {
  await page.getByRole('button', { name: `Actions for ${cardRef}`, exact: true }).focus()
  await page.keyboard.press('Enter')
  const items = page.locator('.v-overlay--active .v-list-item')
  await expect(items.first()).toBeVisible()
  return items
}

/** Picks a stage from a card's ⋯ menu ("Move to stage"), from the keyboard. */
export async function moveFromMenu(page: Page, cardRef: string, stage: string): Promise<void> {
  const items = await openCardMenu(page, cardRef)
  await items.filter({ has: page.locator('.v-list-item-title', { hasText: new RegExp(`^${stage}$`) }) }).click()
}

/**
 * Drags a card with the real mouse, in steps, as a person does: SortableJS
 * draws its own copy and needs the pointer to travel.
 */
export async function dragCard(page: Page, card: Locator, target: Locator, hold?: () => Promise<void>): Promise<void> {
  await card.scrollIntoViewIfNeeded()
  const from = await card.boundingBox()
  await target.scrollIntoViewIfNeeded()
  const to = await target.boundingBox()
  if (!from || !to) throw new Error('card or column not on screen')
  await page.mouse.move(from.x + 24, from.y + 12)
  await page.mouse.down()
  await page.mouse.move(from.x + 40, from.y + 30, { steps: 5 })
  await page.mouse.move(to.x + to.width / 2, to.y + 80, { steps: 20 })
  await hold?.()
  await page.mouse.up()
}

/** The snackbar the board shows after an action or a refusal. */
export function boardToast(page: Page): Locator {
  return page.locator('.v-snackbar__content')
}
