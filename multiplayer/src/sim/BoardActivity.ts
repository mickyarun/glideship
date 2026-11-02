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
 * Board work the Garden shows as ambience: a card reaching done, a card
 * handed over to Delivery, a BUD delivered. The backend publishes it on
 * `board_activity:<org_id>` and the bridge hands it to the org's room, which
 * re-broadcasts the checked event to its clients as `board_activity`. The
 * room keeps no state for it; celebrations are client-side.
 *
 * A members-only board's event carries only its kind and actor; the board
 * and card keys come only from boards the whole org can see. Anything else
 * in the payload is dropped, so nothing the backend didn't mean to share
 * reaches a client.
 */
import { isUuid } from "../bridge/uuid"

/** The message name clients listen on. */
export const BOARD_ACTIVITY_MESSAGE = "board_activity"

export const BOARD_ACTIVITY_KINDS = ["card_done", "handover", "bud_delivered"] as const
export type BoardActivityKind = (typeof BOARD_ACTIVITY_KINDS)[number]

export interface BoardActivityEvent {
  kind: BoardActivityKind
  /** The member who did it, or null (an automatic delivery). */
  actor_id: string | null
  board_key?: string
  card_key?: string
}

// Board keys are 2–10 letters; a card key adds `-<number>` (see the backend's
// BOARD_KEY_PATTERN and card keys).
const BOARD_KEY = /^[A-Z]{2,10}$/
const CARD_KEY = /^[A-Z]{2,10}-[0-9]{1,10}$/

function isKind(value: unknown): value is BoardActivityKind {
  return typeof value === "string" && (BOARD_ACTIVITY_KINDS as readonly string[]).includes(value)
}

/**
 * Runtime validator for the cross-process payload. Returns null when the
 * kind or actor is malformed; keys that don't look like keys are dropped.
 */
export function parseBoardActivityEvent(raw: unknown): BoardActivityEvent | null {
  if (!raw || typeof raw !== "object") return null
  const d = raw as Record<string, unknown>
  if (!isKind(d.kind)) return null
  if (d.actor_id !== null && !isUuid(d.actor_id)) return null
  const event: BoardActivityEvent = { kind: d.kind, actor_id: d.actor_id }
  if (typeof d.board_key === "string" && BOARD_KEY.test(d.board_key)) {
    event.board_key = d.board_key
    if (typeof d.card_key === "string" && CARD_KEY.test(d.card_key)) {
      event.card_key = d.card_key
    }
  }
  return event
}
