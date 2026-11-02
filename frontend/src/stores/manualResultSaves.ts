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

/**
 * Manual QA results still being saved, per BUD.
 *
 * The Testing tab shows a picked result at once and saves it behind the
 * scenes. Leaving testing checks the saved results, so it waits for these
 * first; otherwise a case marked a moment before the move still reads as
 * pending and the "cases still pending" dialog opens for nothing.
 */
const inFlight = new Map<string, Set<Promise<unknown>>>()

/** Registers a result save for `budId` and hands it back unchanged. */
export function trackResultSave<T>(budId: string, save: Promise<T>): Promise<T> {
  const saves = inFlight.get(budId) ?? new Set<Promise<unknown>>()
  inFlight.set(budId, saves)
  saves.add(save)
  const done = (): void => {
    saves.delete(save)
    if (saves.size === 0 && inFlight.get(budId) === saves) inFlight.delete(budId)
  }
  save.then(done, done)
  return save
}

/** Resolves once every result save for `budId` has finished, failed ones included. */
export async function resultSavesSettled(budId: string): Promise<void> {
  // A save started while waiting is waited for too.
  for (let saves = inFlight.get(budId); saves?.size; saves = inFlight.get(budId)) {
    await Promise.allSettled([...saves])
  }
}
