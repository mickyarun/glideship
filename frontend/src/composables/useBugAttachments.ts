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

import { ref } from 'vue'
import api from '@/services/api'
import { extractApiError } from '@/utils/errors'
import { DEFAULT_ATTACHMENT_LIMITS, attachmentRejectionReason } from '@/utils/attachments'
import {
  BUG_ATTACHMENT_WIRE,
  filesOf,
  type AttachmentLimits,
  type AttachmentWire,
  type StoredAttachment,
} from '@/utils/attachmentWire'

/**
 * CRUD over one parent's attachments (a bug's, a board card's), at
 * ``{baseUrl}/attachments``; ``wire`` says how that API spells them.
 *
 * Lives outside the stores because attachments are scoped to the single
 * parent currently open, not to board-wide state — and because the bug
 * create dialog needs to upload a staged batch against a bug that does
 * not exist until `createBug` returns.
 *
 * The limits ride along with every list response, so the picker knows
 * the real caps without a separate settings fetch.
 */
export function useBugAttachments(wire: AttachmentWire = BUG_ATTACHMENT_WIRE) {
  const items = ref<StoredAttachment[]>([])
  const limits = ref<AttachmentLimits>({ ...DEFAULT_ATTACHMENT_LIMITS })
  const loading = ref(false)
  const uploading = ref(false)
  const error = ref<string | null>(null)

  // Which parent `items` currently describes. The bug create dialog stays
  // mounted for the life of the page and reuses this one instance for
  // every bug filed, so without an explicit target the previous bug's
  // uploads keep accumulating in `items` and count against the next
  // bug's cap — the second report of a session would be rejected as
  // "limit reached" with nothing attached to it.
  const target = ref<string | null>(null)

  /** Point the list at `baseUrl`, clearing it when the parent changes. */
  function retarget(baseUrl: string): void {
    if (target.value === baseUrl) return
    target.value = baseUrl
    items.value = []
  }

  /** Load a parent's attachments and its current limits. */
  async function load(baseUrl: string): Promise<void> {
    retarget(baseUrl)
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get(`${baseUrl}/attachments`)
      const reply = wire.list(data)
      items.value = reply.items
      limits.value = reply.limits
    } catch (err) {
      error.value = extractApiError(err, 'Failed to load attachments.')
    } finally {
      loading.value = false
    }
  }

  /**
   * Load just the limits, for a parent that doesn't exist yet.
   *
   * The bug create dialog stages files before `createBug` runs, so it has
   * no list response to read limits from. Falling back to the shipped
   * defaults would wrongly reject a file that an org with a higher cap
   * allows, so fetch the real ones up front. A failure here is silent:
   * the defaults remain, and the server is the real gate either way.
   */
  async function loadLimits(): Promise<void> {
    if (!wire.limitsPath || !wire.limits) return
    try {
      const { data } = await api.get(wire.limitsPath)
      limits.value = wire.limits(data)
    } catch {
      // Keep the defaults — this is a hint, not a control.
    }
  }

  /**
   * Upload one file and append it to the list on success.
   *
   * @returns The stored attachment, or `null` when the upload failed
   *   (in which case `error` carries the reason).
   */
  async function upload(baseUrl: string, file: File): Promise<StoredAttachment | null> {
    retarget(baseUrl)
    const reason = attachmentRejectionReason(file, limits.value, filesOf(items.value).length)
    if (reason) {
      error.value = reason
      return null
    }

    uploading.value = true
    error.value = null
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post(`${baseUrl}/attachments`, form)
      const stored = wire.item(data)
      items.value.push(stored)
      return stored
    } catch (err) {
      error.value = extractApiError(err, `Failed to upload "${file.name}".`)
      return null
    } finally {
      uploading.value = false
    }
  }

  /**
   * Upload several files in sequence, stopping at the first failure.
   *
   * Sequential rather than parallel on purpose: the cap is enforced
   * server-side with a count-then-insert, so a parallel burst could slip
   * past it, and a shared connection makes several large uploads slower
   * in parallel anyway. Stopping on the first failure keeps the surfaced
   * error the one that actually happened rather than the last of several.
   *
   * @returns The attachments that were stored before any failure.
   */
  async function uploadMany(baseUrl: string, files: File[]): Promise<StoredAttachment[]> {
    const stored: StoredAttachment[] = []
    for (const file of files) {
      const saved = await upload(baseUrl, file)
      if (!saved) break
      stored.push(saved)
    }
    return stored
  }

  /** Attach a link (parents whose wire takes links). */
  async function addLink(baseUrl: string, url: string, title: string | null): Promise<boolean> {
    retarget(baseUrl)
    error.value = null
    try {
      const { data } = await api.post(`${baseUrl}/attachments/links`, { url, title })
      items.value.push(wire.item(data))
      return true
    } catch (err) {
      error.value = extractApiError(err, "Couldn't add the link.")
      return false
    }
  }

  /** Delete an attachment, removing it from the list on success. */
  async function remove(baseUrl: string, attachmentId: string): Promise<boolean> {
    error.value = null
    try {
      await api.delete(`${baseUrl}/attachments/${attachmentId}`)
      items.value = items.value.filter((a) => a.id !== attachmentId)
      return true
    } catch (err) {
      error.value = extractApiError(err, 'Failed to delete the attachment.')
      return false
    }
  }

  /** Path of the authenticated download endpoint for one attachment. */
  function downloadPath(baseUrl: string, attachmentId: string): string {
    return `${baseUrl}/attachments/${attachmentId}`
  }

  function clearError(): void {
    error.value = null
  }

  return {
    items,
    limits,
    loading,
    uploading,
    error,
    load,
    loadLimits,
    upload,
    uploadMany,
    addLink,
    remove,
    downloadPath,
    clearError,
  }
}
