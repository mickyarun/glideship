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
 * The overall rating: the one place that maps the stored band to the words
 * on screen (pure). Bands are stored 1–5 with 1 the best; screens show only
 * the words, lowest on the left and highest on the right.
 */

export interface Band {
  /** The stored value: 1 is the best, 5 the lowest. */
  value: number
  label: string
  /** One line on what the rating means. */
  meaning: string
}

/** Lowest first, so a row of them reads left to right from low to high. */
export const BANDS: Band[] = [
  { value: 5, label: 'Did not meet', meaning: 'Missed most of what the role needs' },
  { value: 4, label: 'Met sometimes', meaning: 'Got there on some things, not others' },
  { value: 3, label: 'Met every time', meaning: 'Did what the role needs, reliably' },
  { value: 2, label: 'Exceeded most times', meaning: 'Often went past what the role needs' },
  { value: 1, label: 'Exceeded every time', meaning: 'Consistently well past the role' },
]

/** The two "Exceeded" bands: each needs two examples (the server's rule too). */
export const HIGH_BANDS = [1, 2]
export const HIGH_BAND_EVIDENCE = 2
/** How screens name the two high bands together. */
export const HIGH_BANDS_NAME = 'Both "Exceeded" ratings'
/** "Did not meet": the manager needs at least one example to move someone here. */
export const LOW_BAND = 5

export function bandLabel(value: number | null | undefined): string {
  return BANDS.find(b => b.value === value)?.label ?? ''
}

export function bandMeaning(value: number | null | undefined): string {
  return BANDS.find(b => b.value === value)?.meaning ?? ''
}

export function isHighBand(value: number | null | undefined): boolean {
  return value != null && HIGH_BANDS.includes(value)
}

/** How many examples a band needs: from the person, or from the manager when they change it. */
export function evidenceNeeded(value: number | null | undefined, byManager: boolean): number {
  if (isHighBand(value)) return HIGH_BAND_EVIDENCE
  return byManager && value === LOW_BAND ? 1 : 0
}
