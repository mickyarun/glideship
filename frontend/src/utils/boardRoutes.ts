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

// Reading a board route's params: a board key the server could have made,
// and a card number. Anything else is "not found" without asking the API.

import { BOARD_KEY_LENGTHS } from '@/constants/boards'

/**
 * A board key: letters only, within the server's lengths. Mirrors
 * BOARD_KEY_PATTERN in backend/app/services/boards/constants.py, with the
 * lengths from GET /boards/limits once they've loaded.
 */
export function isBoardKey(raw: unknown, lengths: { min: number; max: number } | null = null): raw is string {
  const { min, max } = lengths ?? BOARD_KEY_LENGTHS
  return typeof raw === 'string' && new RegExp(`^[A-Z]{${min},${max}}$`).test(raw.toUpperCase())
}

/** A card number from the URL: digits only, from 1; null otherwise. */
export function parseCardNumber(raw: unknown): number | null {
  if (typeof raw !== 'string' || !/^\d+$/.test(raw)) return null
  const n = Number(raw)
  return Number.isSafeInteger(n) && n >= 1 ? n : null
}

/** The route of a card named by its key ("PDT-1") on its board; null when the key has no number. */
export function cardRouteByKey(boardKey: string, cardKey: string) {
  const number = parseCardNumber(cardKey.slice(cardKey.lastIndexOf('-') + 1))
  return number ? { name: 'board-card', params: { key: boardKey, number } } : null
}
