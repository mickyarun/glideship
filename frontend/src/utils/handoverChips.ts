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

// A card's BUD chips: their tone and words, the "1 of 2 in prod" roll-up,
// and merging a socket copy of a card (whose chips always say
// ``can_open_bud: false``) without losing what the last fetch said.

import { BUD_STATUS_LABELS, type BUDStatus } from '@/types'
import type { CardSummary, HandoverChip } from '@/types/boards'

export type ChipTone = 'done' | 'off' | 'active'

const SHIPPED: readonly BUDStatus[] = ['prod', 'closed']
/** A BUD goes back to its card only before development starts (where a card can land). */
const RETURNABLE: readonly BUDStatus[] = ['bud', 'design', 'tech_arch']

export function canSendBack(status: BUDStatus | null | undefined): boolean {
  return !!status && RETURNABLE.includes(status)
}

export function isShipped(status: BUDStatus | null | undefined): boolean {
  return !!status && SHIPPED.includes(status)
}

/** Shipped is done, discarded (or sent back) is off, anything else is moving. */
export function chipTone(status: BUDStatus | null | undefined, returned = false): ChipTone {
  if (returned || status === 'discarded') return 'off'
  return isShipped(status) ? 'done' : 'active'
}

/** The stage's theme colour (``stage-tech-arch``); closed reads as prod, discarded as neutral. */
export function statusColor(status: BUDStatus | null | undefined, returned = false): string {
  if (returned || !status || status === 'discarded') return 'on-surface-variant'
  return `stage-${(status === 'closed' ? 'prod' : status).replace('_', '-')}`
}

export function statusLabel(status: BUDStatus | null | undefined): string {
  return status ? BUD_STATUS_LABELS[status] : 'Deleted'
}

/** "BUD-012 · Design", or "BUD-012 · Returned" once sent back. */
export function chipLabel(chip: HandoverChip): string {
  const status = chip.handover_status === 'returned' ? 'Returned' : statusLabel(chip.status)
  return `${chip.bud_key} · ${status}`
}

/** "2 of 3 in prod" over the live handovers; null with none live. */
export function deliveryRollup(chips: HandoverChip[]): string | null {
  const live = chips.filter(c => c.handover_status === 'active')
  if (!live.length) return null
  return `${live.filter(c => isShipped(c.status)).length} of ${live.length} in prod`
}

/** A socket copy's chips, each keeping the ``can_open_bud`` the card last had. */
export function keepBudAccess<C extends CardSummary>(incoming: C, held: CardSummary | null | undefined): C {
  if (!incoming.handovers?.length) return incoming
  const known = new Map((held?.handovers ?? []).map(c => [c.bud_id, c.can_open_bud]))
  return { ...incoming, handovers: incoming.handovers.map(c => ({ ...c, can_open_bud: known.get(c.bud_id) ?? false })) }
}
