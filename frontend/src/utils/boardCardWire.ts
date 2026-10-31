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

// How a card's comments and attachments are spelt on the wire, for the
// shared comment thread (stores/commentThread.ts) and attachment strip
// (composables/useAttachmentStrip.ts).

import type { CommentWire, ThreadComment } from '@/stores/commentThread'
import type { CardAttachmentList, CardAttachmentRead, CardCommentPage, CardCommentRead } from '@/types/boards'
import type { AttachmentWire, StoredAttachment } from '@/utils/attachmentWire'
import { importSourceLabel } from '@/utils/importSummary'

function comment(c: CardCommentRead): ThreadComment {
  return {
    id: c.id,
    authorId: c.author_id,
    // An imported comment keeps its original author's name as a label.
    authorName: c.author_name ?? c.author_label,
    authorAvatarUrl: c.author_avatar_url,
    importLabel: importSourceLabel(c.import_source),
    body: c.body,
    editedAt: c.edited_at,
    deletedAt: c.deleted_at,
    createdAt: c.created_at,
  }
}

export const CARD_COMMENT_WIRE: CommentWire = {
  page: data => {
    const page = data as CardCommentPage
    return { items: page.items.map(comment), next: page.next_cursor }
  },
  one: data => comment(data as CardCommentRead),
}

function attachment(a: CardAttachmentRead): StoredAttachment {
  return {
    id: a.id,
    kind: a.kind,
    filename: a.filename,
    url: a.url,
    mimeType: a.mime_type ?? '',
    sizeBytes: a.size_bytes ?? 0,
    uploadedBy: a.uploaded_by,
    createdAt: a.created_at,
  }
}

export const CARD_ATTACHMENT_WIRE: AttachmentWire = {
  list: data => {
    const reply = data as CardAttachmentList
    return {
      items: reply.items.map(attachment),
      limits: {
        maxFileMb: reply.limits.max_file_mb,
        maxFiles: reply.limits.max_files,
        acceptedExtensions: reply.limits.accepted_extensions,
      },
    }
  },
  item: data => attachment(data as CardAttachmentRead),
  links: true,
}
