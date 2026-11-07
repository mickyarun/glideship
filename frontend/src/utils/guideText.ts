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

/** Turning a guide text file into headings, paragraphs and lists (pure). */

export type GuideBlock =
  | { kind: 'heading'; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; items: string[] }

/**
 * "## " starts a heading, lines starting "- " make a list, and blank lines
 * separate paragraphs. Nothing else is markup, so the text is shown as text.
 */
export function guideBlocks(source: string): GuideBlock[] {
  const blocks: GuideBlock[] = []
  for (const chunk of source.split(/\n\s*\n/)) {
    const lines = chunk.split('\n').map(l => l.trim()).filter(Boolean)
    if (!lines.length) continue
    if (lines[0].startsWith('## ')) {
      blocks.push({ kind: 'heading', text: lines[0].slice(3) })
      lines.shift()
      if (!lines.length) continue
    }
    if (lines.every(l => l.startsWith('- '))) {
      blocks.push({ kind: 'list', items: lines.map(l => l.slice(2)) })
    } else {
      blocks.push({ kind: 'paragraph', text: lines.join(' ') })
    }
  }
  return blocks
}
