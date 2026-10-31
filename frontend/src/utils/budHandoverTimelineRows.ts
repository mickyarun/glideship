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

// A BUD's timeline rows for its trips between a board card and Delivery:
// handed over from a card (as a new BUD, again after a send-back, or
// linked), and sent back to it with the reason. Registered with the rest
// in utils/budTimelineRows.ts.

import type { TimelineEvent } from '@/types'
import { actor, section, text, type ActivityPart, type ActivityRow } from '@/utils/activity'
import { statusColor, statusLabel, type Detail } from '@/utils/budTimelineFormat'

const cardOf = (d: Detail): ActivityPart => section(typeof d?.card_key === 'string' && d.card_key ? d.card_key : 'a board card')

function landed(d: Detail): ActivityPart[] {
  const at = typeof d?.target_status === 'string' ? d.target_status : ''
  return at ? [text('Landed at'), { kind: 'status', text: statusLabel(at), color: statusColor(at) }] : []
}

export const HANDOVER_ROWS: Record<string, (event: TimelineEvent, d: Detail) => ActivityRow> = {
  handed_over_from_board: (e, d) => {
    if (d?.linked) return { primary: [...actor(e.actor_name), text('linked this BUD to'), cardOf(d)] }
    const words = d?.again ? 'handed this BUD over again from' : 'handed this BUD over from'
    return { primary: [...actor(e.actor_name), text(words), cardOf(d)], meta: landed(d) }
  },
  returned_to_board: (e, d) => ({
    primary: [...actor(e.actor_name), text('sent this BUD back to'), cardOf(d)],
    lines: typeof d?.reason === 'string' && d.reason ? [`Reason: ${d.reason}`] : [],
  }),
}
