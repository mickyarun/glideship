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

// Taking someone to a field on a card's page: the board's "Open card" after
// a refused move links to the page with ``?focus=<field>``, and the page
// (or its own refused move) brings that field into view and focuses its
// first control. Each field's place on the page carries
// ``data-card-field="<field>"``; the PRD lives on the Documents tab.

import type { StageRequiredField } from '@/types/boards'
import { REQUIRED_FIELDS } from '@/utils/stageRules'

export const FOCUS_QUERY_KEY = 'focus'

/** The card page tab each field is on. */
export function tabFor(field: StageRequiredField): 'overview' | 'documents' {
  return field === 'prd' ? 'documents' : 'overview'
}

/** The field named in the URL, or null for anything else. */
export function focusFrom(value: unknown): StageRequiredField | null {
  return REQUIRED_FIELDS.find(f => f === value) ?? null
}

const CONTROLS = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Scroll a field into view and focus its first control; false when it isn't on the page. */
export function focusField(field: StageRequiredField, root: ParentNode = document): boolean {
  const place = root.querySelector<HTMLElement>(`[data-card-field="${field}"]`)
  if (!place) return false
  place.scrollIntoView?.({ block: 'center' })
  const control = place.matches(CONTROLS) ? place : place.querySelector<HTMLElement>(CONTROLS)
  control?.focus({ preventScroll: true })
  return true
}
