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

// A link the page may render from data it didn't write (a repository's
// URL from the server, say): only an https:// address is followed. Anything
// else (javascript:, data:, a relative path, plain http) comes back null,
// and the caller shows the name as text instead.

const SAFE_SCHEME = 'https:'

export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    return new URL(url).protocol === SAFE_SCHEME ? url : null
  } catch {
    return null
  }
}
