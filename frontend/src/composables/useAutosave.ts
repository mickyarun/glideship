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
 * Save as you type.
 *
 * Compares a snapshot of the form with the last one saved, so loading a
 * record never saves it, text typed while a save is on its way is kept and
 * saved next, and saves never overlap. Leaving the page saves what's left,
 * and closing the tab while something is unsaved asks first.
 */

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const DELAY_MS = 800

export type SaveState = 'saved' | 'saving' | 'unsaved' | 'failed'

/** What the form's footer says for each state. */
export const SAVE_WORDS: Record<SaveState, string> = {
  saved: 'Saved as you type',
  saving: 'Saving…',
  unsaved: 'Saving…',
  failed: "Couldn't save. Keep typing to try again.",
}

/**
 * @param snapshot The form as a string; a change starts the clock.
 * @param persist Saves the form as it is now; returns a problem or null.
 * @param canSave Whether the caller may save at all.
 */
export function useAutosave(snapshot: () => string, persist: () => Promise<string | null>, canSave: () => boolean) {
  const state = ref<SaveState>('saved')
  const problem = ref('')
  let saved = snapshot()
  let timer: ReturnType<typeof setTimeout> | undefined
  let running: Promise<void> | null = null

  function schedule(): void {
    clearTimeout(timer)
    timer = setTimeout(() => void save(), DELAY_MS)
  }

  async function run(): Promise<void> {
    const sending = snapshot()
    state.value = 'saving'
    const failed = await persist()
    problem.value = failed ?? ''
    if (failed) {
      state.value = 'failed'
      return
    }
    saved = sending
    state.value = snapshot() === saved ? 'saved' : 'unsaved'
  }

  async function save(): Promise<void> {
    clearTimeout(timer)
    // Another call may start a save while this one waits: wait for all of them.
    while (running) await running
    if (!canSave() || snapshot() === saved) {
      state.value = 'saved'
      problem.value = ''
      return
    }
    running = run()
    await running
    running = null
    if (state.value === 'unsaved') schedule()
  }

  /** Takes the form as it is now as saved: call after loading a record. */
  function reset(): void {
    clearTimeout(timer)
    saved = snapshot()
    state.value = 'saved'
    problem.value = ''
  }

  /** Saves now, before sending; whether everything typed is saved. */
  async function flush(): Promise<boolean> {
    await save()
    return state.value === 'saved'
  }

  watch(snapshot, now => {
    if (!canSave() || now === saved) return
    state.value = 'unsaved'
    schedule()
  })

  // The browser's own "leave this page?" while text is still on its way.
  function warn(event: BeforeUnloadEvent): void {
    if (!canSave() || (!running && snapshot() === saved)) return
    event.preventDefault()
    // Older browsers ask only when this is set.
    event.returnValue = ''
  }

  onMounted(() => window.addEventListener('beforeunload', warn))
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', warn)
    clearTimeout(timer)
    if (canSave() && snapshot() !== saved) void save()
  })

  return { state, problem, reset, flush }
}
