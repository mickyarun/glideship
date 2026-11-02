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

// One async refresh at a time: a call while one runs asks for one more run
// after it (so nothing that changed mid-flight is missed) instead of a
// second request alongside it.

/** Wrap `task` so overlapping calls share a run, plus at most one more. */
export function coalesced(task: () => Promise<void>): () => Promise<void> {
  let running: Promise<void> | null = null
  let again = false
  return () => {
    if (running) {
      again = true
      return running
    }
    running = (async () => {
      try {
        do {
          again = false
          await task()
        } while (again)
      } finally {
        running = null
      }
    })()
    return running
  }
}

/**
 * One save at a time per key, latest wins: a call while that key's save
 * runs replaces any value already waiting, and the waiting one is sent
 * after, so saves never overlap or land out of order. Every caller for a
 * run resolves with the last save's outcome.
 */
export function latestWins<K, V>(save: (key: K, value: V) => Promise<boolean>): (key: K, value: V) => Promise<boolean> {
  const running = new Map<K, Promise<boolean>>()
  const waiting = new Map<K, V>()
  return (key, value) => {
    const held = running.get(key)
    if (held) {
      waiting.set(key, value)
      return held
    }
    const run = (async () => {
      let ok = await save(key, value)
      while (waiting.has(key)) {
        const next = waiting.get(key) as V
        waiting.delete(key)
        ok = await save(key, next)
      }
      running.delete(key)
      return ok
    })()
    running.set(key, run)
    return run
  }
}
