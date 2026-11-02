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
/** The attachment strip's short limits line and when to show its file count. */
import type { AttachmentLimits } from '@/utils/attachmentWire'

/** File kinds in the order the hint names them, each with its extensions. */
const KINDS: ReadonlyArray<{ name: string; extensions: readonly string[] }> = [
  { name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'heic', 'bmp'] },
  { name: 'PDF', extensions: ['pdf'] },
  { name: 'docs', extensions: ['doc', 'docx', 'odt', 'rtf', 'txt', 'md'] },
  { name: 'sheets', extensions: ['xls', 'xlsx', 'ods', 'csv'] },
  { name: 'slides', extensions: ['ppt', 'pptx', 'odp', 'key'] },
  { name: 'archives', extensions: ['zip', 'gz', 'tar'] },
  { name: 'video', extensions: ['mp4', 'mov', 'webm'] },
]

/** Share of the file limit at which the strip starts showing "x / limit". */
export const NEAR_LIMIT_SHARE = 0.8

const bare = (extension: string): string => extension.replace(/^\./, '').toLowerCase()

/** The accepted extensions as kinds people recognise: "Images, PDF, docs". */
export function acceptedKinds(extensions: readonly string[]): string[] {
  const accepted = new Set(extensions.map(bare))
  const kinds = KINDS.filter(k => k.extensions.some(e => accepted.has(e))).map(k => k.name)
  const known = new Set(KINDS.flatMap(k => k.extensions))
  const others = [...accepted].filter(e => !known.has(e)).map(e => e.toUpperCase())
  return [...kinds, ...others]
}

/** "Images, PDF, docs · up to 10 MB each" — shown only to people who can upload. */
export function attachmentHint(limits: AttachmentLimits): string {
  const kinds = acceptedKinds(limits.acceptedExtensions)
  const size = `up to ${limits.maxFileMb} MB each`
  return kinds.length ? `${kinds.join(', ')} · ${size}` : size
}

/** Whether the "x / limit" count is worth showing: near or at the limit. */
export function nearFileLimit(count: number, maxFiles: number): boolean {
  return maxFiles > 0 && count >= Math.ceil(maxFiles * NEAR_LIMIT_SHARE)
}
