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

// Builders for stage-agent tests: an agent on a stage, a run, a skill, a
// card's AI panel reply, an AI draft, and a refusal with a code (and a
// Retry-After header).

import { AxiosError, AxiosHeaders } from 'axios'
import type { AgentRunRead, BoardSkillOption, CardAgents, DocRead, StageAgentRead } from '@/types/boards'

export function makeAgent(id: string, over: Partial<StageAgentRead> = {}): StageAgentRead {
  return {
    id, stage_id: 's1', skill_id: `sk-${id}`, skill_name: 'PRD writer', skill_slug: 'board-prd-writer',
    agent_type: 'boardPrd', output_kind: 'prd', trigger: 'manual', enabled: true, order: 0, ...over,
  }
}

export function makeRun(id: string, over: Partial<AgentRunRead> = {}): AgentRunRead {
  return {
    id, card_id: '3', stage_id: 's1', stage_agent_id: 'a1', skill_id: 'sk-a1', trigger: 'manual',
    status: 'running', job_id: `job-${id}`, attempt: 1, result_summary: null, error_message: null,
    error_code: null, triggered_by: 'me', started_at: '2026-10-31T10:00:00Z', finished_at: null,
    created_at: '2026-10-31T10:00:00Z',
    ...over,
  }
}

export function makeSkill(id: string, name: string, over: Partial<BoardSkillOption> = {}): BoardSkillOption {
  return { id, name, slug: id, agent_type: 'custom', suggested: false, output_kind: 'notes', ...over }
}

export function cardAgents(over: Partial<CardAgents> = {}): CardAgents {
  return { ai_enabled: true, agents: [makeAgent('a1')], runs: [], active: null, ...over }
}

export function makeDraft(version: number, body_md: string, over: Partial<DocRead> = {}): DocRead {
  return {
    id: `draft${version}`, kind: 'prd', state: 'pending_review', version, source: 'agent', agent_run_id: 'r1',
    created_by: null, created_at: '2026-10-31T10:05:00Z', body_md, ...over,
  }
}

/** A refusal with the ``code`` the server sends beside ``detail``, and its headers. */
export function codedError(status: number, code: string | null, detail = 'Refused', headers: Record<string, string> = {}): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', String(status), config, null, {
    status, statusText: '', headers, config, data: code ? { detail, code } : { detail },
  })
}
