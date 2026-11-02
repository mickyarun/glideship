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

// What a card's Delivery panel says after a handover or a retry: a message
// naming the BUD, with Open BUD when I may open it. A BUD that landed at
// design with its designs still to start keeps its message up with "Start
// designs", which opens the BUD: its page starts them (``design_pending``).

import { useRouter } from 'vue-router'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'
import { useBudAccess } from '@/composables/useBudAccess'
import type { HandoverResult } from '@/types/boards'

type Feedback = ReturnType<typeof useBoardFeedback>

export function useHandoverOutcome(feedback: () => Feedback) {
  const router = useRouter()
  const { canOpen } = useBudAccess()

  function report(result: HandoverResult, text: string): void {
    const { handover } = result
    const budId = handover.bud_id
    const open = budId && canOpen(handover) ? () => void router.push(`/buds/${budId}`) : null
    const designs = result.design_available && !!open
    feedback().show({
      text: designs ? `${text}. Its designs start when you open it.` : text,
      action: open ? { label: designs ? 'Start designs' : 'Open BUD', run: open } : undefined,
      persist: designs,
    })
    feedback().announce(text)
  }

  /** "PDT-1 handed over as BUD-002", or "linked to" for a link. */
  function handedOver(result: HandoverResult): void {
    const { handover, card } = result
    report(result, handover.linked_existing ? `${card.key} linked to ${handover.bud_key}` : `${card.key} handed over as ${handover.bud_key}`)
  }

  function restarted(result: HandoverResult): void {
    report(result, `Started the agents for ${result.handover.bud_key}`)
  }

  return { handedOver, restarted }
}
