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

// What an import call's failure means to the person: the server's own
// message when it sent one (it names the cap, the stage or the limit),
// a plain sentence when it didn't, and how long to wait before trying
// again when the server said (Retry-After on 429 and 503, capped).

import { MAX_RETRY_AFTER_SECONDS } from '@/constants/imports'
import { extractApiError } from '@/utils/errors'

export interface ImportFailure {
  message: string
  status: number | null
  /** The server's machine-readable reason (e.g. STAGE_GONE), when it sent one. */
  code: string | null
  /** Seconds the server asked us to wait, or null to retry at will. */
  retryAfter: number | null
}

/** Sentences for one call's statuses, ahead of the general ones. */
export type FailureTexts = Partial<Record<number, string>>

/** A stage the mapping uses was removed from the board: the review must change. */
export const STAGE_GONE = 'STAGE_GONE'

const FALLBACK: Record<number, string> = {
  404: "This import isn't there any more. Start a new one.",
  409: 'Another import is still open. Finish or wait for it, then try again.',
  413: 'That file is too large to import here. Import bigger boards over a Trello connection.',
  422: "That file doesn't look like a Trello board export.",
  429: "You've started a lot of imports lately. Try again a little later.",
  503: 'Imports are busy right now. Try again in a moment.',
}

interface HttpLike {
  message?: unknown
  response?: {
    status?: number
    data?: { code?: unknown }
    headers?: Record<string, unknown> & { get?: (name: string) => unknown }
  }
}

/**
 * Retry-After as seconds (a number of seconds or an HTTP date), at most
 * MAX_RETRY_AFTER_SECONDS; null when absent or odd.
 */
export function parseRetryAfter(value: unknown, now = Date.now()): number | null {
  if (value === null || value === undefined || value === '') return null
  const text = String(value).trim()
  const at = Date.parse(text)
  const seconds = /^\d+$/.test(text) ? Number(text) : Number.isNaN(at) ? null : Math.ceil((at - now) / 1000)
  return seconds === null ? null : Math.min(MAX_RETRY_AFTER_SECONDS, Math.max(0, seconds))
}

function header(err: HttpLike, name: string): unknown {
  const headers = err.response?.headers
  if (!headers) return null
  if (typeof headers.get === 'function') return headers.get(name)
  return headers[name] ?? headers[name.toLowerCase()]
}

/**
 * Read an import request's failure. With no detail from the server, `texts`
 * (this call's own sentences) come first, then the general ones, then
 * `fallback`.
 */
export function importFailure(err: unknown, fallback: string, texts: FailureTexts = {}): ImportFailure {
  const response = (err as HttpLike | null)?.response
  const status = response?.status ?? null
  const own = status === null ? undefined : texts[status] ?? FALLBACK[status]
  const message = extractApiError(err, own || fallback)
  const retryAfter = status === 429 || status === 503 ? parseRetryAfter(header(err as HttpLike, 'retry-after')) : null
  const code = typeof response?.data?.code === 'string' ? response.data.code : null
  return { message, status, code, retryAfter }
}

/** What to log about a failed call: its message and status, never the request or response. */
export function failureLog(err: unknown): string {
  const e = err as HttpLike | null
  const message = typeof e?.message === 'string' ? e.message : String(err)
  return e?.response?.status ? `${message} (HTTP ${e.response.status})` : message
}
