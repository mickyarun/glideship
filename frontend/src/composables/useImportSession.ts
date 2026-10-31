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

// One import session, followed live. The session row is the truth: every
// job event (on the job socket) and the board's one board_imported
// summary just re-read it, and the wizard's step comes from its status.
// Request failures keep the server's text and its Retry-After.

import { computed, ref } from 'vue'
import { useJobSocket } from '@/composables/useJobSocket'
import { useRetryCountdown } from '@/composables/useRetryCountdown'
import { useTopicChannel } from '@/composables/useTopicChannel'
import { boardImportsApi } from '@/services/boardImportsApi'
import { boardTopic, type BoardSocketMessage, type ImportAccepted, type ImportSessionRead } from '@/types/boards'
import { importFailure, type ImportFailure } from '@/utils/importErrors'

export type ImportStep = 'source' | 'map' | 'import' | 'done'

/** Where the wizard stands for a session (none yet: choosing a source). */
export function stepFor(session: ImportSessionRead | null): ImportStep {
  if (!session) return 'source'
  switch (session.status) {
    case 'pending':
    case 'parsing':
      return 'source'
    case 'ready':
      return 'map'
    case 'running':
      return 'import'
    case 'completed':
      return 'done'
    default:
      // A failed read goes back to the source; a failed run offers Resume.
      return !session.discovery ? 'source' : !session.mapping ? 'map' : 'import'
  }
}

export function useImportSession() {
  const session = ref<ImportSessionRead | null>(null)
  const busy = ref(false)
  const failure = ref<ImportFailure | null>(null)
  const countdown = useRetryCountdown()
  const job = useJobSocket()
  let lastPct = -1

  const step = computed(() => stepFor(session.value))
  const reading = computed(() => ['pending', 'parsing'].includes(session.value?.status ?? ''))
  const running = computed(() => session.value?.status === 'running')

  function fail(err: unknown, fallback: string): void {
    failure.value = importFailure(err, fallback)
    countdown.wait(failure.value.retryAfter)
  }

  async function refresh(): Promise<void> {
    const id = session.value?.id
    if (!id) return
    try {
      const next = await boardImportsApi.get(id)
      if (session.value?.id === id) session.value = next
    } catch (err) {
      fail(err, "Couldn't check on the import. Reload the page to see where it stands.")
    }
  }

  function follow(jobId: string | null): void {
    if (!jobId) return
    lastPct = -1
    job.startTracking(jobId, {
      // Each batch moves the bar; the counts come from the session row.
      onProgress: status => {
        if (status.progressPct === lastPct || status.state === 'completed' || status.state === 'failed') return
        lastPct = status.progressPct
        if (running.value) void refresh()
      },
      onComplete: () => void refresh(),
      onError: () => void refresh(),
      onMissing: () => void refresh(),
    })
  }

  /** Open a session by id (a link back, or a reload) and follow its job. */
  async function load(id: string): Promise<boolean> {
    busy.value = true
    failure.value = null
    try {
      session.value = await boardImportsApi.get(id)
      if (reading.value || running.value) follow(session.value.job_id)
      return true
    } catch (err) {
      fail(err, "Couldn't open this import.")
      return false
    } finally {
      busy.value = false
    }
  }

  /** Send a request that queues a job (create, start, resume) and follow it. */
  async function queue(request: () => Promise<ImportAccepted>, fallback: string): Promise<boolean> {
    if (busy.value || countdown.waiting.value) return false
    busy.value = true
    failure.value = null
    try {
      const accepted = await request()
      session.value = await boardImportsApi.get(accepted.sessionId)
      follow(accepted.jobId)
      return true
    } catch (err) {
      fail(err, fallback)
      // A refused start can still change the session (a full queue marks it failed).
      await refresh()
      return false
    } finally {
      busy.value = false
    }
  }

  const start = () => {
    const id = session.value?.id
    return id ? queue(() => boardImportsApi.start(id), "Couldn't start the import. Try again.") : Promise.resolve(false)
  }

  function reset(): void {
    job.stopTracking()
    session.value = null
    failure.value = null
    countdown.wait(null)
  }

  // The board hears one summary when a run ends; it covers a dropped job socket.
  useTopicChannel<BoardSocketMessage>(
    () => (session.value?.board_id ? boardTopic(session.value.board_id) : null),
    {
      board_imported: message => {
        if (message.session_id === session.value?.id) void refresh()
      },
    },
    () => void refresh(),
  )

  return {
    session, step, reading, running, busy, failure, countdown,
    load, queue, start, refresh, reset, fail,
  }
}

export type ImportSession = ReturnType<typeof useImportSession>
