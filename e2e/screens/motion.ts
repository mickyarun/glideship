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
 * Waiting for the page to stop moving. Vuetify dialogs and menus animate in,
 * and some do things when the animation ends: a dialog that has slid in
 * takes focus back into itself, which closes a menu opened inside it in the
 * meantime.
 */
import { expect, type Page } from '@playwright/test'

// Far past any menu or dialog transition in the app.
const SETTLE_MS = 5_000

/**
 * Animations still running that will end: endless ones (spinners, the
 * garden) never settle and one with no effect paints nothing, so neither
 * counts. Runs in the page, so it uses nothing from this module.
 */
function finiteAnimationsRunning(): string[] {
  return document.getAnimations()
    .filter((a) => a.playState === 'running' && a.effect !== null
      && a.effect.getComputedTiming().endTime !== Infinity)
    .map((a) => (a as CSSAnimation).animationName ?? (a as CSSTransition).transitionProperty ?? (a.id || 'unnamed'))
}

/** Resolves once nothing on the page is part way through a transition. */
export async function settled(page: Page, what: string): Promise<void> {
  await expect.poll(() => page.evaluate(finiteAnimationsRunning), {
    message: `animations still running on ${what}`,
    timeout: SETTLE_MS,
  }).toEqual([])
}
