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

// Moving a card to another board, worked out before it's sent: which
// boards it can go to, the stage it lands in, and what it loses on the
// way. Mirrors backend/app/services/boards/card_board_move.py (the stage
// rule, labels by name, assignees who can edit the target, a linked
// repository); the server decides, this is the preview.

import type {
  BoardListItem, BoardPersonRead, BoardRepoRead, BoardRole, CardSummary, CustomBoardItem, LabelRead, StageRead,
} from '@/types/boards'
import { wordList } from '@/utils/format'

/** Roles that may move cards onto a board (``move_card``). */
const EDIT_ROLES: ReadonlySet<BoardRole> = new Set(['editor', 'admin'])

/** What the move dialog knows about the board it's moving to. */
export interface MoveTarget {
  key: string
  name: string
  stages: StageRead[]
  labels: LabelRead[]
  people: BoardPersonRead[]
  repos: BoardRepoRead[]
}

/** The card's facts on the source board, to work out what it keeps. */
export interface MoveSource {
  card: CardSummary
  labels: LabelRead[]
  people: BoardPersonRead[]
}

/** Boards I edit, other than this one; Delivery isn't a move (it's a handover). */
export function moveTargets(items: BoardListItem[], fromKey: string): CustomBoardItem[] {
  return items.filter(
    (b): b is CustomBoardItem => b.kind === 'custom' && b.key !== fromKey && EDIT_ROLES.has(b.role),
  )
}

/** The server's pick: the same name, else the first of the same category, else the default stage. */
export function landingStage(stages: StageRead[], from: Pick<StageRead, 'name' | 'category'> | null): StageRead | null {
  const ordered = [...stages].sort((a, b) => a.position - b.position)
  const name = from?.name.trim().toLowerCase()
  return (
    ordered.find(s => !!name && s.name.trim().toLowerCase() === name)
    ?? ordered.find(s => !!from && s.category === from.category)
    ?? ordered.find(s => s.is_default)
    ?? ordered[0]
    ?? null
  )
}

const lower = (name: string) => name.trim().toLowerCase()
const editors = (people: BoardPersonRead[]) => new Set(people.filter(p => EDIT_ROLES.has(p.role)).map(p => p.id))

/** The card as it arrives: target label ids by name, only assignees who can edit there. */
export function arriving(source: MoveSource, target: MoveTarget): CardSummary {
  const byName = new Map(target.labels.map(l => [lower(l.name), l.id]))
  const names = source.labels.filter(l => source.card.label_ids.includes(l.id)).map(l => lower(l.name))
  const keep = editors(target.people)
  const repoLinked = target.repos.some(r => r.id === source.card.repo_id)
  return {
    ...source.card,
    label_ids: names.map(n => byName.get(n)).filter((id): id is string => !!id),
    assignee_ids: source.card.assignee_ids.filter(id => keep.has(id)),
    repo_id: repoLinked ? source.card.repo_id : null,
  }
}

/** What the card loses on the way: label names the target lacks, assignees who can't edit it, its repository. */
export interface MoveLosses {
  labels: string[]
  assignees: string[]
  repo: boolean
}

export function moveLosses(source: MoveSource, target: MoveTarget): MoveLosses {
  const { card } = source
  const targetNames = new Set(target.labels.map(l => lower(l.name)))
  const keep = editors(target.people)
  return {
    labels: source.labels.filter(l => card.label_ids.includes(l.id) && !targetNames.has(lower(l.name))).map(l => l.name),
    assignees: card.assignee_ids.filter(id => !keep.has(id)),
    repo: !!card.repo_id && !target.repos.some(r => r.id === card.repo_id),
  }
}

/** The preview's lines: the new key, then what's dropped, removed or cleared. */
export function moveChanges(source: MoveSource, target: MoveTarget): string[] {
  const lost = moveLosses(source, target)
  const lines = [`Gets the next ${target.name} number; links to ${source.card.key} keep working.`]
  if (lost.labels.length) lines.push(`Labels not on ${target.name} are dropped: ${lost.labels.join(', ')}`)
  if (lost.assignees.length) lines.push(`Removed: ${peopleWords(lost.assignees, source.people)}, who can't edit ${target.name}`)
  if (lost.repo) lines.push(`Repository cleared: not linked on ${target.name}`)
  return lines
}

/** "Pat and Sam", or "Pat and 1 other" for people this board doesn't name. */
export function peopleWords(ids: string[], people: BoardPersonRead[]): string {
  const named = ids.map(id => people.find(p => p.id === id)?.name).filter((n): n is string => !!n)
  const others = ids.length - named.length
  if (!others) return wordList(named)
  if (!named.length) return `${others} ${others === 1 ? 'person' : 'people'}`
  return wordList([...named, `${others} ${others === 1 ? 'other' : 'others'}`])
}
