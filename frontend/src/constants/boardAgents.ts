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

// AI on board stages: the words, icon and timings the settings section,
// the card's AI panel and the board's tiles share.

import type { AgentRunRead, AgentRunStatus, AgentTrigger, CardAgentRun, CardDocKind } from '@/types/boards'

/** The spark that marks AI on a board (settings, the card panel, a tile's chip). */
export const AI_ICON = 'mdi-creation-outline'

/** The two triggers, as the settings' pill toggle offers them. */
export const AGENT_TRIGGER_OPTIONS: { value: AgentTrigger; label: string }[] = [
  { value: 'on_enter', label: 'When a card enters' },
  { value: 'manual', label: 'Only by hand' },
]

/** A trigger mid-sentence, for the card's panel ("Runs when a card enters Design"). */
export function triggerWords(trigger: AgentTrigger, stageName: string): string {
  return trigger === 'on_enter' ? `When a card enters ${stageName}, or by hand` : 'By hand, from this card'
}

/** Runs still going: one per card at most. */
export const ACTIVE_RUN_STATUSES: ReadonlySet<AgentRunStatus> = new Set(['pending', 'running'])

/** How often a running run's elapsed time ticks. */
export const RUN_ELAPSED_TICK_MS = 1000

/** How a run that ended reads at the top of the card's AI panel. */
export const RUN_ENDED_TITLES: Partial<Record<AgentRunStatus, (skill: string) => string>> = {
  failed: skill => `${skill} didn't finish`,
  canceled: skill => `${skill} was canceled`,
}

const STOPPED = 'It was stopped before it wrote a draft.'
const UNFINISHED = 'The run stopped before it wrote a draft.'

/** A sentence's end, so the panel's own words can follow a message that has none. */
const SENTENCE_END = /[.!?…]$/

/** Why a run ended: the run's own words (a stale run, a restart, a cancel's reason), else what its status means. */
export function runEndedWords(run: Pick<AgentRunRead, 'status' | 'error_message'>): string {
  const own = run.error_message?.trim()
  if (!own) return run.status === 'canceled' ? STOPPED : UNFINISHED
  return SENTENCE_END.test(own) ? own : `${own}.`
}

/** A tile's AI chip, naming the skill when the card's summary does. */
export function chipTitle(run: CardAgentRun): string {
  if (!run.skill_name) return run.status === 'pending' ? 'AI run queued' : 'AI running'
  return `${run.skill_name} ${run.status === 'pending' ? 'queued' : 'running'}`
}

/** What a skill writes, as the stage picker hints it. */
export const DOC_WRITES: Record<CardDocKind, string> = {
  prd: 'writes a PRD',
  design_brief: 'writes a design brief',
  notes: 'writes notes',
}

/** What the board's AI switch says, in settings and when it's off on a card. */
export const AI_SWITCH_NOTE =
  'Agents write drafts for a person to accept. They never move cards or hand them over. When this is off, every agent below is paused.'
export const AI_OFF_NOTE = 'A board admin turned AI off. Existing drafts stay; no new runs start.'

/** The Delivery board's AI switch, in its settings. */
export const DELIVERY_AI_NOTE = "When off, BUD stage agents don't start; per-BUD agent choices stay as they are."
export const DELIVERY_AI_READONLY = 'Only people who can change organization settings can switch this.'
