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

// What a refused move to another board says, for the refusals the target
// stage's entry rules don't cover, and what the dialog does next: a 404
// for the card means it moved or went away meanwhile, one for the board
// means the target is gone from my list (reload it), and a 429 waits as
// long as the server asks (Retry-After).

import { extractApiError } from '@/utils/errors'

interface Reply {
  response?: { status?: number; data?: { detail?: unknown } }
}

const STAGE_GONE = 'Stage not found.'
const CARD_GONE = 'Card not found.'

/** What a 404 lost: the card itself, the target stage, or the target board. */
export type MoveLost = 'card' | 'stage' | 'board'

export function moveLost(err: unknown): MoveLost | null {
  const response = (err as Reply | null)?.response
  if (response?.status !== 404) return null
  const detail = response.data?.detail
  if (detail === CARD_GONE) return 'card'
  return detail === STAGE_GONE ? 'stage' : 'board'
}

/** What a refused move says. */
export function moveError(err: unknown, targetName: string, cardKey: string): string {
  const status = (err as Reply | null)?.response?.status
  if (status === 403) return `You need edit access on both boards to move this card to ${targetName}.`
  switch (moveLost(err)) {
    case 'card':
      return `${cardKey} isn't on this board any more: it moved or was deleted meanwhile.`
    case 'stage':
      return `That stage isn't on ${targetName} any more. Pick another one.`
    case 'board':
      return `${targetName} isn't available to you any more. Pick another board.`
    default:
      return extractApiError(err, "Couldn't move the card. Try again.")
  }
}

/** "Try again in 12s", for a move held back by the server's rate limit. */
export function waitWords(seconds: number): string {
  return `You've moved a lot of cards between boards just now. Try again in ${seconds}s.`
}

/** The card an open move dialog was for left its board or was archived by someone else. */
export const MOVED_MEANWHILE = 'This card moved or was archived meanwhile.'
