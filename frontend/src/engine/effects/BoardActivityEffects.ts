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
 * BoardActivityEffects — board work shown in the Garden as ambience, from
 * the org room's `board_activity` message (no XP, no state):
 *
 *   - card_done      → the actor's character plays the Cheer emote (the
 *                      exact KayKit track `Cheering`), when they're in the
 *                      garden and standing idle;
 *   - handover       → the CelebrationBurst toast and confetti;
 *   - bud_delivered  → the same.
 *
 * Toasts never name a card's title; they give the card or board key only
 * when the event carries one (members-only boards send none). A burst of
 * events shows one toast per `TOAST_GAP_MS`.
 */
import type { BoardActivityEvent } from '../../multiplayer/boardActivity'
import { showCelebration } from './CelebrationBurst'

/** How long a finished card's cheer plays, in seconds. */
export const CARD_DONE_CHEER_S = 3
/** At most one board toast this often, in milliseconds. */
export const TOAST_GAP_MS = 4000

export interface BoardActivityTargets {
  /** Cheer on a server-driven character; false when it can't (absent, walking, seated). */
  cheer: (userId: string, seconds: number) => boolean
  /** The member under local control, and their own cheer; null outside takeover. */
  takeover: () => { userId: string; cheer: () => void } | null
  /** The positioned element over the canvas that toasts go in. */
  overlay: () => HTMLElement | null
}

/** What the toast says, or null for an event that shows none. */
export function boardActivityMessage(event: BoardActivityEvent): string | null {
  const card = event.card_key ?? (event.board_key ? `A ${event.board_key} card` : null)
  if (event.kind === 'handover') return `${card ?? 'A card'} handed over to Delivery`
  if (event.kind === 'bud_delivered') return card ? `${card} delivered` : 'Board work delivered'
  return null
}

export class BoardActivityEffects {
  private lastToastAt = Number.NEGATIVE_INFINITY

  constructor(
    private readonly targets: BoardActivityTargets,
    private readonly now: () => number = () => performance.now(),
  ) {}

  handle(event: BoardActivityEvent): void {
    if (event.kind === 'card_done') {
      this.cheer(event.actor_id)
      return
    }
    const message = boardActivityMessage(event)
    const overlay = this.targets.overlay()
    if (!message || !overlay) return
    const at = this.now()
    if (at - this.lastToastAt < TOAST_GAP_MS) return
    this.lastToastAt = at
    showCelebration(overlay, message)
  }

  private cheer(actorId: string | null): void {
    if (!actorId) return
    const local = this.targets.takeover()
    if (local?.userId === actorId) {
      local.cheer()
      return
    }
    this.targets.cheer(actorId, CARD_DONE_CHEER_S)
  }
}
