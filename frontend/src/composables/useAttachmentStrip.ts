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

import { computed, ref, watch } from 'vue'
import { useBugAttachments } from '@/composables/useBugAttachments'
import { filesOf, type AttachmentWire } from '@/utils/attachmentWire'
import { acceptAttribute, attachmentRejectionReason } from '@/utils/attachments'
import { attachmentHint, nearFileLimit } from '@/utils/attachmentHint'
import { type AttachmentTileRow, stagedTiles, storedTiles } from '@/utils/attachmentTiles'

/**
 * Where the strip's files live: a stored parent (its API path, e.g.
 * ``/v1/bugs/{id}``), or files staged by the component's parent.
 */
export interface AttachmentStripSource {
  baseUrl: () => string | null
  staged: () => File[]
  setStaged: (files: File[]) => void
  /** How the parent's API spells attachments; bugs by default. */
  wire?: AttachmentWire
}

/**
 * State and actions behind BugAttachments.vue, in either of two modes:
 *
 * - **stored** (`baseUrl` set) — reads and writes through the API.
 * - **staged** (`baseUrl` null) — holds picked files with the parent until
 *   it has a bug to attach them to. The create dialog needs this because
 *   attachments are keyed on a bug that doesn't exist until the user hits
 *   "Report Bug".
 *
 * Both modes render the same strip, so a reporter sees no difference
 * between attaching before and after the bug is filed.
 */
export function useAttachmentStrip(source: AttachmentStripSource) {
  const attachments = useBugAttachments(source.wire)
  const { items, limits, loading, uploading } = attachments
  const localError = ref<string | null>(null)

  const isStaging = computed(() => !source.baseUrl())
  const stored = () => source.baseUrl() as string
  const files = computed(() => filesOf(items.value))
  const links = computed(() => items.value.filter(a => a.kind === 'link'))

  // Both modes read the org's real limits: stored mode gets them with
  // the list, staging mode fetches them on mount (there is no bug to
  // list). `limits` starts at the shipped defaults, so the picker is
  // usable during that first round-trip.
  const effectiveLimits = computed(() => limits.value)

  const count = computed(() => (isStaging.value ? source.staged().length : files.value.length))
  const isFull = computed(() => count.value >= effectiveLimits.value.maxFiles)
  const accept = computed(() => acceptAttribute(effectiveLimits.value))
  const hint = computed(() => attachmentHint(effectiveLimits.value))
  const nearLimit = computed(() => nearFileLimit(count.value, effectiveLimits.value.maxFiles))

  // One message slot, fed by whichever layer failed — a client-side
  // rejection, a failed request, or a tile that couldn't fetch its blob.
  const message = computed({
    get: () => localError.value ?? attachments.error.value,
    set: (value: string | null) => {
      localError.value = value
      if (value === null) attachments.clearError()
    },
  })

  const tiles = computed<AttachmentTileRow[]>(() =>
    isStaging.value
      ? stagedTiles(source.staged())
      : storedTiles(files.value, id => attachments.downloadPath(stored(), id)),
  )

  async function addFiles(picked: File[]): Promise<void> {
    if (isStaging.value) stageFiles(picked)
    else await attachments.uploadMany(stored(), picked)
  }

  function stageFiles(picked: File[]): void {
    const next = [...source.staged()]
    for (const file of picked) {
      const reason = attachmentRejectionReason(file, effectiveLimits.value, next.length)
      if (reason) {
        message.value = reason
        break
      }
      next.push(file)
    }
    source.setStaged(next)
  }

  function removeTile(tile: AttachmentTileRow): void {
    message.value = null
    if (isStaging.value) {
      source.setStaged(source.staged().filter((f) => f !== tile.file))
      return
    }
    void attachments.remove(stored(), tile.key)
  }

  async function addLink(url: string, title: string | null): Promise<boolean> {
    message.value = null
    return !isStaging.value && attachments.addLink(stored(), url, title)
  }

  function removeLink(id: string): void {
    message.value = null
    if (!isStaging.value) void attachments.remove(stored(), id)
  }

  /**
   * Upload the staged files to a parent (a bug) that now exists.
   *
   * Called by the create dialog once `createBug` returns an id. Files
   * that land are dropped from the staged list; any that fail stay put
   * and visible, with the reason in the message slot, so the reporter
   * can retry them instead of losing them on close.
   *
   * @returns True when every staged file was stored.
   */
  async function flush(baseUrl: string): Promise<boolean> {
    if (!source.staged().length) return true
    const landed = await attachments.uploadMany(baseUrl, source.staged())
    // uploadMany stops at the first failure, so the successes are always
    // the leading slice of what was staged.
    const remaining = source.staged().slice(landed.length)
    source.setStaged(remaining)
    return remaining.length === 0
  }

  /** Reload the stored list (another person changed it). */
  function reload(): void {
    if (!isStaging.value) void attachments.load(stored())
  }

  // Reload whenever the panel switches to a different parent, and clear
  // any message left over from the previous one.
  watch(
    source.baseUrl,
    (baseUrl) => {
      localError.value = null
      attachments.clearError()
      // A parent's list response carries the limits; without one, fetch
      // them on their own so the staged picker validates against the
      // real caps rather than the shipped defaults.
      if (baseUrl) void attachments.load(baseUrl)
      else void attachments.loadLimits()
    },
    { immediate: true },
  )

  return {
    loading, uploading, effectiveLimits, count, isFull, nearLimit, accept, hint, message, tiles, items,
    links, addFiles, removeTile, addLink, removeLink, flush, reload,
  }
}
