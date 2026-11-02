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

// Stage agents, their runs on cards, and the skills a stage can use.
// Mirrors backend/app/schemas/boards/agent.py, BoardAgentTrigger and
// BoardAgentRunStatus in models/board_agent.py, and AgentType in
// models/agent_skill.py.

import type { CardDocKind } from '@/types/boards/doc'

/** When an agent runs: as a card enters its stage, or from the card's Run button. */
export type AgentTrigger = 'on_enter' | 'manual'
export type AgentRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled'

/** Why a run ended without a draft (runs that ended before codes existed have none). */
export type AgentRunErrorCode =
  | 'AI_NOT_CONFIGURED'
  | 'PROVIDER_FAILED'
  | 'TIMEOUT'
  | 'QUEUE_FULL'
  | 'SKILL_GONE'
  | 'STALE'
  | 'INTERRUPTED'
  | 'CANCELED'
  | 'OVER_LIMIT'
  | 'UNKNOWN'

/**
 * One agent for a stage, as the admin's list sends it (lowest ``order`` runs
 * first). ``id`` keeps one of the stage's agents; without it one is added.
 */
export interface StageAgentWrite {
  id?: string
  skill_id: string
  trigger: AgentTrigger
  enabled: boolean
  order: number
}

/** One of a stage's agents, with the skill it runs. */
export interface StageAgentRead {
  id: string
  stage_id: string
  skill_id: string
  skill_name: string
  skill_slug: string
  agent_type: string
  output_kind: CardDocKind
  trigger: AgentTrigger
  enabled: boolean
  order: number
}

/** A skill from the org's library a stage can run; the two board skills are ``suggested``. */
export interface BoardSkillOption {
  id: string
  name: string
  slug: string
  agent_type: string
  suggested: boolean
  output_kind: CardDocKind
}

export interface AgentRunRead {
  id: string
  card_id: string
  stage_id: string | null
  stage_agent_id: string | null
  skill_id: string | null
  trigger: AgentTrigger
  status: AgentRunStatus
  job_id: string | null
  attempt: number
  result_summary: Record<string, unknown> | null
  /**
   * The raw reason, sent to board admins only (null for everyone else and
   * on live updates): people read the words for ``error_code``.
   */
  error_message: string | null
  error_code: AgentRunErrorCode | null
  triggered_by: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

/** A queued run (202): follow ``job_id`` on the job socket. */
export interface AgentRunAccepted {
  job_id: string
  run: AgentRunRead
}

/**
 * A card's AI panel: the switched-on agents of its stage, its latest runs
 * (newest first), the one going now, and the board's AI switch.
 */
export interface CardAgents {
  ai_enabled: boolean
  agents: StageAgentRead[]
  runs: AgentRunRead[]
  active: AgentRunRead | null
}

/** The codes a refused run, cancel or stage-agent change sends beside ``detail``. */
export type AgentErrorCode =
  | 'AI_DISABLED'
  | 'AGENT_RUN_ACTIVE'
  | 'SKILL_NOT_IN_LIBRARY'
  | 'AGENT_RUN_LIMIT'
  | 'AGENT_RUN_FINISHED'
