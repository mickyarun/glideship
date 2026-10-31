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

// The target board's stages as a card arriving there meets them: which
// ones it can't enter yet and why (the stage picker's locks), the stage
// it lands in when the server's pick is locked (the first one that takes
// it), and a dead end the move itself causes: a stage that needs an
// assignee when every assignee is removed (they can't edit the target), or
// a label when every label is dropped (the target lacks them). Filling
// the card in on its own board can't fix those, so the dialog offers
// another stage instead of "Open card".

import type { StageRead, StageRequiredField } from '@/types/boards'
import { arriving, landingStage, moveLosses, peopleWords, type MoveSource, type MoveTarget } from '@/utils/boardMove'
import { wordList } from '@/utils/format'
import { blockReason, missingFor, needsList, needsSentence } from '@/utils/stageRules'

/** A target stage in the picker, locked (with the reason) when the arriving card can't enter it. */
export interface MoveStageItem {
  id: string
  name: string
  reason: string | undefined
}

/** The landing stage: the server's pick, or the first that takes the card when that one is locked. */
export interface MoveLanding {
  stage: StageRead | null
  /** The server's pick, when it was locked and another was chosen. */
  instead: StageRead | null
}

const ordered = (stages: StageRead[]) => [...stages].sort((a, b) => a.position - b.position)

export function moveStageItems(source: MoveSource, target: MoveTarget): MoveStageItem[] {
  const card = arriving(source, target)
  return ordered(target.stages).map(s => ({ id: s.id, name: s.name, reason: blockReason(card, s) }))
}

/** The first stage the arriving card can enter, in board order. */
export function openStage(source: MoveSource, target: MoveTarget): StageRead | null {
  const card = arriving(source, target)
  return ordered(target.stages).find(s => !blockReason(card, s)) ?? null
}

export function moveLanding(source: MoveSource, target: MoveTarget, from: StageRead | null): MoveLanding {
  const picked = landingStage(target.stages, from)
  if (!picked || !blockReason(arriving(source, target), picked)) return { stage: picked, instead: null }
  const open = openStage(source, target)
  return open ? { stage: open, instead: picked } : { stage: picked, instead: null }
}

/** Fields ``stage`` needs that the card has now and loses on the way. */
function lostFields(source: MoveSource, target: MoveTarget, stage: StageRead): StageRequiredField[] {
  const had = new Set(missingFor(source.card, stage))
  return missingFor(arriving(source, target), stage).filter(f => !had.has(f))
}

/**
 * Why ``stage`` refuses the card when the move causes it ("Emma Clarke
 * can't edit SEO, so Writing would have no assignee."), with anything
 * else it needs after; null when the card could be filled in to enter.
 */
export function moveDeadEnd(source: MoveSource, target: MoveTarget, stage: StageRead): string | null {
  const lost = lostFields(source, target, stage)
  if (!lost.length) return null
  const losses = moveLosses(source, target)
  const parts: string[] = []
  if (lost.includes('assignee')) {
    parts.push(`${peopleWords(losses.assignees, source.people)} can't edit ${target.name}, so ${stage.name} would have no assignee.`)
  }
  if (lost.includes('label')) {
    const verb = losses.labels.length === 1 ? "isn't" : "aren't"
    parts.push(`${wordList(losses.labels)} ${verb} on ${target.name}, so ${stage.name} would have no label.`)
  }
  const rest = missingFor(arriving(source, target), stage).filter(f => !lost.includes(f))
  if (rest.length) parts.push(`It also needs ${needsList(rest)}.`)
  return parts.join(' ')
}

/** Why the server's pick was passed over, and what was picked instead. */
export function landingNote(source: MoveSource, target: MoveTarget, landing: MoveLanding): string | null {
  const { stage, instead } = landing
  if (!stage || !instead) return null
  const missing = missingFor(arriving(source, target), instead)
  const why = moveDeadEnd(source, target, instead) ?? needsSentence(instead.name, missing)
  return `${why} ${stage.name} is picked instead.`
}
