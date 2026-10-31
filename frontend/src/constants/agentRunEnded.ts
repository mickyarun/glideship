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

// How a run that ended without a draft reads on the card's AI panel. The
// words come from the run's ``error_code``, never from its raw
// ``error_message`` (that goes to the console only). A server that sends
// no code yet gets the default words, except a run whose message says no
// AI provider is set up, which reads as AI_NOT_CONFIGURED.

import type { AgentRunErrorCode, AgentRunRead, AgentRunStatus } from '@/types/boards'

const NOTHING_CHANGED = 'Nothing on the card changed.'

/** The headline above the words. */
export const RUN_ENDED_TITLES: Partial<Record<AgentRunStatus, (skill: string) => string>> = {
  failed: skill => `${skill} didn't finish`,
  canceled: skill => `${skill} was canceled`,
}

export const RUN_ENDED_COPY: Record<AgentRunErrorCode, string> = {
  AI_NOT_CONFIGURED: "The AI service isn't connected for your organization. An admin can set it up in Settings › AI.",
  PROVIDER_FAILED: `The AI service ran into a problem while drafting. ${NOTHING_CHANGED}`,
  TIMEOUT: `The AI service took too long, so the run was stopped. ${NOTHING_CHANGED}`,
  QUEUE_FULL: 'AI is busy right now. Try again in a minute.',
  SKILL_GONE: "This agent's skill was removed. An admin can pick another in board settings.",
  STALE: 'The run stopped before it finished. Try again.',
  INTERRUPTED: 'The run stopped before it finished. Try again.',
  CANCELED: 'Canceled.',
}

export const RUN_ENDED_DEFAULT = `Something went wrong while drafting. ${NOTHING_CHANGED}`

/** Words in a code-less run's message that mean no AI provider is set up (lower case). */
const NOT_CONFIGURED_HINTS = ['cli not found', 'not configured']

const isCode = (code: unknown): code is AgentRunErrorCode => typeof code === 'string' && code in RUN_ENDED_COPY

type Ended = Pick<AgentRunRead, 'status' | 'error_message' | 'error_code'>

/** Why the run ended, as a code: the server's, else what its status or message implies. */
export function runEndedCode(run: Ended): AgentRunErrorCode | null {
  if (isCode(run.error_code)) return run.error_code
  if (run.status === 'canceled') return 'CANCELED'
  const raw = run.error_message?.toLowerCase() ?? ''
  return NOT_CONFIGURED_HINTS.some(hint => raw.includes(hint)) ? 'AI_NOT_CONFIGURED' : null
}

/** What the panel says about a run that ended. */
export function runEndedWords(run: Ended): string {
  const code = runEndedCode(run)
  return code ? RUN_ENDED_COPY[code] : RUN_ENDED_DEFAULT
}
