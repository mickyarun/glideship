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

// A line-by-line diff of two texts (the ``diff`` package's diffLines), as
// rows for common/DiffView.vue, and how many lines each side changed.

import { diffLines } from 'diff'

export interface DiffLine {
  type: 'added' | 'removed' | 'context'
  text: string
}

/** The rows from ``oldText`` to ``newText``; none when they're the same. */
export function lineDiff(oldText: string, newText: string): DiffLine[] {
  if (oldText === newText) return []
  const out: DiffLine[] = []
  for (const chunk of diffLines(oldText, newText)) {
    const type: DiffLine['type'] = chunk.added ? 'added' : chunk.removed ? 'removed' : 'context'
    for (const line of chunk.value.replace(/\n$/, '').split('\n')) out.push({ type, text: line })
  }
  return out
}

/** Lines added and removed, or null when nothing changed. */
export function diffStats(lines: DiffLine[]): { added: number; removed: number } | null {
  let added = 0
  let removed = 0
  for (const line of lines) {
    if (line.type === 'added') added += 1
    else if (line.type === 'removed') removed += 1
  }
  return added || removed ? { added, removed } : null
}
