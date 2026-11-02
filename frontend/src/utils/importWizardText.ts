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

// The import wizard's words: its steps, the line under the title once a
// board is read, and the error to show (a refused request, or a session
// whose board couldn't be read, which starting it again reads afresh).

import type { WizardStep } from '@/components/boards/imports/ImportStepper.vue'
import type { ImportStep } from '@/composables/useImportSession'
import type { ImportMode, ImportSessionRead } from '@/types/boards'
import { IMPORT_CODES, type ImportFailure } from '@/utils/importErrors'
import { plural } from '@/utils/format'

export interface WizardProblem {
  title: string
  text: string
  /** Starting the session again is the fix (it reads the board afresh). */
  retry: boolean
}

/** Titles for a refused request while choosing a source (creating an import). */
const SOURCE_TITLES: Record<number, string> = {
  413: 'That file is too large',
  429: 'Too many imports started',
  503: 'Imports are busy',
}

/** Titles once an import exists (saving its review, starting it). */
const RUN_TITLES: Record<number, string> = {
  429: 'Try again shortly',
  503: 'Imports are busy',
}

/** Titles for coded refusals, whatever the step. */
const CODE_TITLES: Record<string, string> = {
  [IMPORT_CODES.tooManyOpen]: 'Too many imports open',
  [IMPORT_CODES.boardKeyTaken]: 'That key is taken',
  [IMPORT_CODES.stageNameTaken]: 'A stage name is taken',
  [IMPORT_CODES.stillWorking]: 'Still importing',
}

/** What a full open-imports cap says to do about it. */
function capAdvice(failure: ImportFailure): string {
  if (failure.code !== IMPORT_CODES.tooManyOpen) return ''
  return failure.facts.scope === 'org'
    ? ' Your team has too many imports running right now; try again later.'
    : ' Continue or discard one of yours to start another.'
}

export function wizardSteps(mode: ImportMode | null, canConnect: boolean): WizardStep[] {
  const first = mode === 'api' ? 'Connect' : mode === 'upload' || !canConnect ? 'Upload' : 'Upload or connect'
  return [
    { id: 'source', label: first },
    { id: 'map', label: 'Map lists and people' },
    { id: 'import', label: 'Import' },
    { id: 'done', label: 'Done' },
  ]
}

/** `"Ops requests" from Trello · uploaded export · 214 cards, 9 lists, 11 members` */
export function wizardSubtitle(session: ImportSessionRead | null): string | undefined {
  const found = session?.discovery
  if (!session || !found) return undefined
  const how = session.mode === 'api' ? 'Trello connection' : 'uploaded export'
  const sizes = [
    plural(found.counts.cards, 'card'),
    plural(found.lists.length, 'list'),
    plural(found.members.length, 'member'),
  ].join(', ')
  return `"${found.board_name}" from Trello · ${how} · ${sizes}`
}

/** An import stopped part-way: its own step says why, so no separate callout. */
export const isStopped = (session: ImportSessionRead | null, step: ImportStep) =>
  step === 'import' && session?.status === 'failed'

export function wizardProblem(
  failure: ImportFailure | null, session: ImportSessionRead | null, step: ImportStep,
): WizardProblem | null {
  if (isStopped(session, step)) return null
  if (failure) {
    const titles = step === 'source' ? SOURCE_TITLES : RUN_TITLES
    const title = (failure.code && CODE_TITLES[failure.code]) || (failure.status && titles[failure.status]) || ''
    return { title, text: `${failure.message}${capAdvice(failure)}`, retry: false }
  }
  if (session?.status === 'failed' && step === 'source') {
    return {
      title: "The board couldn't be read",
      text: session.error || 'Something stopped the read part-way.',
      retry: true,
    }
  }
  return null
}
