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

// Logging a failed call without what it carried: the error's message and
// HTTP status only, never the request or the response (their headers and
// bodies can hold tokens, emails or a card's text). Every board and import
// call logs through here.

interface HttpLike {
  message?: unknown
  response?: { status?: number }
}

/** What to log about a failed call: its message and status, never the request or response. */
export function failureLog(err: unknown): string {
  const e = err as HttpLike | null
  const message = typeof e?.message === 'string' ? e.message : String(err)
  return e?.response?.status ? `${message} (HTTP ${e.response.status})` : message
}

/** "[boards] people fetch failed: Network Error (HTTP 503)". */
export function logFailure(scope: string, what: string, err: unknown): void {
  console.error(`[${scope}] ${what} failed:`, failureLog(err))
}
