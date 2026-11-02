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
 * Shared number formatting utilities.
 */

/** Format skill points: show integers without decimals, fractional with 2 places. */
export function formatSP(sp: number): string {
  return Number.isInteger(sp) ? sp.toString() : sp.toFixed(2)
}

/** A count with its noun: ``plural(1, 'person', 'people')`` → "1 person". */
export function plural(n: number, word: string, many = `${word}s`): string {
  return `${n} ${n === 1 ? word : many}`
}

/** Words as a phrase: "a", "a and b", "a, b and c" (or ``or``). */
export function wordList(words: string[], conjunction = 'and'): string {
  if (words.length < 2) return words[0] ?? ''
  return `${words.slice(0, -1).join(', ')} ${conjunction} ${words[words.length - 1]}`
}
