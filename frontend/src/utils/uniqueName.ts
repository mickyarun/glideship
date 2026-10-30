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

// One rule for names that must be unique on a board (stages, labels).

/** Why ``name`` can't be used for a ``what`` (trimmed first), or null when it can. */
export function uniqueNameBlock(
  items: readonly { id: string; name: string }[],
  name: string,
  exceptId: string | null,
  what: string,
): string | null {
  const trimmed = name.trim()
  if (!trimmed) return `Give the ${what} a name.`
  const taken = items.some(i => i.id !== exceptId && i.name.trim() === trimmed)
  return taken ? `Another ${what} on this board already has that name.` : null
}
