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

/** Team boards and their cards, set up through the real boards API. */
import { randomInt } from 'node:crypto'
import type { Api } from './api.ts'

export type Template = 'blank' | 'content-seo' | 'design' | 'ops' | 'product'
export type BoardRole = 'viewer' | 'editor' | 'admin'
export type RequiredField = 'assignee' | 'due_date' | 'priority' | 'label' | 'description' | 'prd'

export interface Stage {
  id: string
  name: string
  category: string
}

export interface Board {
  id: string
  key: string
  name: string
  stages: Stage[]
}

export interface Card {
  id: string
  key: string
  number: number
  title: string
  stage_id: string
}

interface BoardDetail {
  board: { id: string; key: string; name: string }
  stages: Stage[]
}

/** A board key no other test will pick: six capital letters. */
export function boardKey(): string {
  return Array.from({ length: 6 }, () => String.fromCharCode(65 + randomInt(26))).join('')
}

/** A board made from a template by ``api``'s member, who becomes its admin. */
export async function createBoard(
  api: Api, template: Template, name: string, fields: Record<string, unknown> = {},
): Promise<Board> {
  const detail = await api.post<BoardDetail>('boards', { name, key: boardKey(), template, ...fields })
  return { ...detail.board, stages: detail.stages }
}

export function stageOf(board: Board, name: string): Stage {
  const stage = board.stages.find(s => s.name === name)
  if (!stage) throw new Error(`${board.key} has no stage "${name}"`)
  return stage
}

/** A card in ``stage`` (the board's default stage when not named). */
export function addCard(
  api: Api, board: Board, title: string, stage?: string, fields: Record<string, unknown> = {},
): Promise<Card> {
  const stageId = stage ? stageOf(board, stage).id : undefined
  return api.post<Card>(`boards/${board.key}/cards`, { title, stage_id: stageId, ...fields })
}

/** What a card must have before it may enter ``stage``. */
export async function requireFields(api: Api, board: Board, stage: string, fields: RequiredField[]): Promise<void> {
  await api.patch(`boards/${board.key}/stages/${stageOf(board, stage).id}`, { required_fields: fields })
}

/** Gives ``userId`` a role on the board. */
export async function addBoardMember(api: Api, board: Board, userId: string, role: BoardRole): Promise<void> {
  await api.put(`boards/${board.key}/members/${userId}`, { role })
}

/** Turns on handing cards over to Delivery, landing BUDs at ``target``. */
export async function enableHandover(api: Api, board: Board, target: 'bud' | 'design' | 'tech_arch'): Promise<void> {
  await api.patch(`boards/${board.key}`, { handover_enabled: true, handover_target_status: target })
}

/** Changes a card's fields (assignees, description, due date…). */
export async function updateCard(api: Api, board: Board, card: Card, fields: Record<string, unknown>): Promise<void> {
  await api.patch(`boards/${board.key}/cards/${card.number}`, fields)
}

/** Adds an open checklist line to a card. */
export async function addChecklistItem(api: Api, board: Board, card: Card, text: string): Promise<void> {
  await api.post(`boards/${board.key}/cards/${card.number}/checklist`, { text })
}
