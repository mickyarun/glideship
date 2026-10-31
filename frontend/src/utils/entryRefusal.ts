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

// A stage's entry rules refusing a move or a create, read from the
// server's reply: 422 STAGE_REQUIREMENTS_MISSING names the missing fields,
// 409 CHECKLIST_OPEN the open checklist items. Anything else isn't one.

import type { StageRequiredField } from '@/types/boards'
import { REQUIRED_FIELDS } from '@/utils/stageRules'

export type EntryRefusal =
  | { code: 'STAGE_REQUIREMENTS_MISSING'; stageId: string; missing: StageRequiredField[] }
  | { code: 'CHECKLIST_OPEN'; open: number; total: number }

interface Reply {
  response?: { status?: number; data?: Record<string, unknown> }
}

const isField = (value: unknown): value is StageRequiredField =>
  REQUIRED_FIELDS.includes(value as StageRequiredField)

export function entryRefusal(err: unknown): EntryRefusal | null {
  const response = (err as Reply | null)?.response
  const data = response?.data
  if (!data || typeof data !== 'object') return null
  if (response.status === 422 && data.code === 'STAGE_REQUIREMENTS_MISSING') {
    const missing = Array.isArray(data.missing) ? data.missing.filter(isField) : []
    return { code: data.code, stageId: String(data.stage_id ?? ''), missing }
  }
  if (response.status === 409 && data.code === 'CHECKLIST_OPEN') {
    return { code: data.code, open: Number(data.open) || 0, total: Number(data.total) || 0 }
  }
  return null
}
