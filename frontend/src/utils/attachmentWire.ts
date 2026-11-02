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

// Attachments as the strip shows them, whichever parent holds them, and
// how each parent's API spells them: bugs answer in camelCase with their
// limits per bug; another parent (a board card) passes its own wire.

import type { BugAttachment, BugAttachmentLimits, BugAttachmentListResponse } from '@/types'

/** What a parent accepts, for the picker to check before uploading. */
export interface AttachmentLimits {
  maxFileMb: number
  /** Files per parent; links don't count. */
  maxFiles: number
  acceptedExtensions: string[]
}

export type AttachmentKind = 'file' | 'link'

export interface StoredAttachment {
  id: string
  kind: AttachmentKind
  filename: string
  /** A link's address; null for a file (download it by id). */
  url: string | null
  mimeType: string
  sizeBytes: number
  uploadedBy: string | null
  createdAt: string
}

export interface AttachmentWire {
  list(data: unknown): { items: StoredAttachment[]; limits: AttachmentLimits }
  item(data: unknown): StoredAttachment
  /** Where the limits live for a parent that doesn't exist yet (staged files). */
  limitsPath?: string
  limits?(data: unknown): AttachmentLimits
  /** The parent takes links as well as files, at ``{baseUrl}/attachments/links``. */
  links: boolean
}

function bugLimits(limits: BugAttachmentLimits): AttachmentLimits {
  return {
    maxFileMb: limits.maxFileMb,
    maxFiles: limits.maxFilesPerBug,
    acceptedExtensions: limits.acceptedExtensions,
  }
}

function bugItem(item: BugAttachment): StoredAttachment {
  return { ...item, kind: 'file', url: null }
}

export const BUG_ATTACHMENT_WIRE: AttachmentWire = {
  list: data => {
    const reply = data as BugAttachmentListResponse
    return { items: reply.items.map(bugItem), limits: bugLimits(reply.limits) }
  },
  item: data => bugItem(data as BugAttachment),
  limitsPath: '/v1/bugs/attachments/limits',
  limits: data => bugLimits(data as BugAttachmentLimits),
  links: false,
}

/** The stored files among a parent's attachments (what the file cap counts). */
export function filesOf(items: StoredAttachment[]): StoredAttachment[] {
  return items.filter(a => a.kind === 'file')
}
