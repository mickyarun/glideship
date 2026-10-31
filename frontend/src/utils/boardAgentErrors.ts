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

// What a refused agent run, or a refused change to a stage's agents, says,
// by the ``code`` the server sends beside ``detail``. A full queue (503)
// and too many runs going at once (429 ``AGENT_RUN_LIMIT``) also say how
// long to wait (Retry-After); Retry is the same call.

import type { AgentErrorCode } from '@/types/boards'
import { extractApiError } from '@/utils/errors'
import { retryAfterOf } from '@/utils/importErrors'

interface Reply {
  response?: { status?: number; data?: { code?: unknown } }
}

/** Statuses that ask the caller to wait (Retry-After) and send the same call again. */
const WAIT_STATUSES: ReadonlySet<number> = new Set([429, 503])
const BUSY = 503
const BUSY_WORDS = 'Too many AI runs are queued right now.'

export interface AgentFailure {
  code: AgentErrorCode | null
  text: string
  /** Seconds to wait before trying again, else null. */
  retryAfter: number | null
}

const MESSAGES: Partial<Record<AgentErrorCode, string>> = {
  AI_DISABLED: 'AI is off for this board. A board admin can turn it on in settings.',
  AGENT_RUN_ACTIVE: 'An agent is already working on this card. Wait for it to finish.',
  SKILL_NOT_IN_LIBRARY: "That skill isn't in your organization's library any more. Pick another one.",
}

const CODES: ReadonlySet<string> = new Set<AgentErrorCode>(['AI_DISABLED', 'AGENT_RUN_ACTIVE', 'SKILL_NOT_IN_LIBRARY', 'AGENT_RUN_LIMIT'])
const isCode = (code: unknown): code is AgentErrorCode => typeof code === 'string' && CODES.has(code)

/** A refusal that waits, with the seconds left on its countdown. */
export function waitWords(text: string, seconds: number): string {
  return seconds > 0 ? `${text} Retry in ${seconds}s.` : `${text} You can try again now.`
}

export function agentFailure(err: unknown, fallback: string): AgentFailure {
  const response = (err as Reply | null)?.response
  const code = isCode(response?.data?.code) ? response.data.code : null
  const status = response?.status ?? 0
  if (WAIT_STATUSES.has(status)) {
    const text = status === BUSY ? BUSY_WORDS : extractApiError(err, fallback)
    return { code, text, retryAfter: retryAfterOf(err) ?? 0 }
  }
  const known = code ? MESSAGES[code] : undefined
  return { code, text: known ?? extractApiError(err, fallback), retryAfter: null }
}
