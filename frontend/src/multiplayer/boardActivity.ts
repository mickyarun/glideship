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
 * Board work the org room re-broadcasts to the Garden as ambience: a card
 * reaching done, a card handed over to Delivery, a BUD delivered. Mirrors
 * multiplayer/src/sim/BoardActivity.ts, which has already checked it; the
 * client checks again because the message crosses a process. A members-only
 * board's event carries only its kind and actor; keys come only from boards
 * the whole org can see, and never a title.
 */

/** The message name the org room broadcasts on. */
export const BOARD_ACTIVITY_MESSAGE = 'board_activity'

export const BOARD_ACTIVITY_KINDS = ['card_done', 'handover', 'bud_delivered'] as const
export type BoardActivityKind = (typeof BOARD_ACTIVITY_KINDS)[number]

export interface BoardActivityEvent {
  kind: BoardActivityKind
  /** The member who did it, or null (an automatic delivery). */
  actor_id: string | null
  board_key?: string
  card_key?: string
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const BOARD_KEY = /^[A-Z]{2,10}$/
const CARD_KEY = /^[A-Z]{2,10}-[0-9]{1,10}$/

function isKind(value: unknown): value is BoardActivityKind {
  return typeof value === 'string' && (BOARD_ACTIVITY_KINDS as readonly string[]).includes(value)
}

/** The event, or null when its kind or actor is malformed; keys that aren't keys are dropped. */
export function parseBoardActivity(raw: unknown): BoardActivityEvent | null {
  if (!raw || typeof raw !== 'object') return null
  const d = raw as Record<string, unknown>
  if (!isKind(d.kind)) return null
  const actor = d.actor_id ?? null
  if (actor !== null && (typeof actor !== 'string' || !UUID.test(actor))) return null
  const event: BoardActivityEvent = { kind: d.kind, actor_id: actor }
  if (typeof d.board_key === 'string' && BOARD_KEY.test(d.board_key)) {
    event.board_key = d.board_key
    if (typeof d.card_key === 'string' && CARD_KEY.test(d.card_key)) event.card_key = d.card_key
  }
  return event
}
