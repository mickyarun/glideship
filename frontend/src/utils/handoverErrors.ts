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

// What a refused handover, link or send-back says, by the ``code`` the
// server sends beside ``detail``. A refusal without one (or with a code
// whose ``detail`` says it best) says the server's own words.

import type { HandoverErrorCode } from '@/types/boards'
import { extractApiError } from '@/utils/errors'

export interface HandoverFailure {
  code: HandoverErrorCode | null
  text: string
}

interface Reply {
  response?: { data?: { code?: unknown; permission?: unknown; status?: unknown } }
}

/** How a permission reads in a sentence. */
const PERMISSION_WORDS: Record<string, string> = {
  'workspace:engineering': 'engineering access',
  'buds:view': 'permission to view BUDs (buds:view)',
  'buds:create': 'permission to create BUDs (buds:create)',
  'buds:edit': 'permission to edit BUDs (buds:edit)',
}

const MESSAGES: Record<HandoverErrorCode, string> = {
  HANDOVER_DISABLED: "This board doesn't hand cards over to Delivery. A board admin can turn it on in settings.",
  HANDOVER_NEEDS_PERMISSION: '',
  HANDOVER_NEEDS_REQUIREMENTS: 'Tech arch needs a PRD or a description on the card. Add one, or land the BUD earlier.',
  BUD_HAS_OTHER_ORIGIN: 'That BUD was already handed over from another card. Pick a different one.',
  BUD_ALREADY_LINKED: 'This card already holds that BUD.',
  BUD_NOT_OPEN: "That BUD is closed or discarded, so it can't be linked.",
  HANDOVER_NOT_ACTIVE: 'This BUD is no longer held by a card, so there is nothing to send it back to.',
  BUD_PAST_RETURN: 'Development has started on this BUD, so it stays here. Raise problems on the BUD, as a comment or a bug.',
  // The server's own words say these best.
  BUD_NOT_RETURNED: '',
  HANDOVER_STAGE_STARTED: 'Those agents have started already.',
}

const isCode = (code: unknown): code is HandoverErrorCode => typeof code === 'string' && code in MESSAGES

export function permissionWords(permission: string): string {
  return PERMISSION_WORDS[permission] ?? `the ${permission} permission`
}

export function handoverFailure(err: unknown, fallback: string): HandoverFailure {
  const data = (err as Reply | null)?.response?.data
  const code = isCode(data?.code) ? data.code : null
  if (code === 'HANDOVER_NEEDS_PERMISSION') {
    const needed = typeof data?.permission === 'string' ? permissionWords(data.permission) : 'more access'
    return { code, text: `Handing over needs ${needed}. Ask an org admin for it.` }
  }
  return { code, text: code && MESSAGES[code] ? MESSAGES[code] : extractApiError(err, fallback) }
}
