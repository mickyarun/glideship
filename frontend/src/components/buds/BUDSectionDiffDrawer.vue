<!--
 * Copyright 2025-2026 Arun Rajkumar
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 -->

<!-- Edit-history drawer for one BUD section.

     Lists snapshots scoped to a single phase (e.g. only the BUD
     phase's snapshots show up when looking at Requirements). Selecting
     a snapshot renders a unified line-level diff against the current
     content. Restore POSTs to /buds/{id}/revert/{phase}/{v}, which
     produces a new ``source='revert'`` row — history is append-only,
     so the restore is itself reversible. -->
<template>
  <!-- A side sheet (a dialog), so nothing sits off-screen beside the page
       while it's closed; full screen on phones, Escape closes it. -->
  <AppSideSheet v-model="open" :title="`${sectionLabel} history`" :width="900">
    <p class="diff-drawer__scope">
      Showing edits to <strong>{{ sectionLabel }}</strong> only · {{ phase }} phase
    </p>

    <div class="diff-drawer__body">
      <!-- Left rail — version list scoped to this phase. -->
      <aside class="diff-rail">
        <VersionRail
          :items="railItems"
          :selected-id="selectedVersion?.id ?? null"
          :loading="loading"
          @select="id => selectById(id)"
        />
      </aside>

      <!-- Right pane — diff viewer. -->
      <section class="diff-pane">
        <header class="diff-pane__header">
          <div class="text-body-2">
            <template v-if="selectedVersion">
              Comparing
              <strong>v{{ selectedVersion.version_no }}</strong>
              ({{ relativeTime(selectedVersion.edited_at, new Date()) }})
              → <strong>current</strong>
            </template>
            <template v-else>
              Select a version to see what changed.
            </template>
          </div>
          <div v-if="diffStats" class="diff-stats">
            <span class="diff-stats__added">+{{ diffStats.added }}</span>
            <span class="diff-stats__removed">−{{ diffStats.removed }}</span>
          </div>
          <v-spacer />
          <v-tooltip :text="restoreDisabledReason || 'Restore this version'" location="top">
            <template #activator="{ props: tipProps }">
              <span v-bind="tipProps">
                <v-btn
                  size="small"
                  color="warning"
                  variant="flat"
                  prepend-icon="mdi-undo"
                  :disabled="!selectedVersion || !!restoreDisabledReason"
                  :loading="restoring"
                  @click="confirmRestore = true"
                >
                  Restore
                </v-btn>
              </span>
            </template>
          </v-tooltip>
        </header>

        <div v-if="loadingDetail" class="diff-pane__placeholder">
          <v-progress-circular indeterminate size="28" />
        </div>
        <div v-else-if="!selectedVersion" class="diff-pane__placeholder">
          <v-icon icon="mdi-arrow-left-circle-outline" size="32" class="text-medium-emphasis" />
          <div class="text-body-2 text-medium-emphasis mt-2">
            Pick a version to view the diff.
          </div>
        </div>
        <DiffView v-else :old="oldText" :new="currentContent" :label="`${sectionLabel} changes`" />
      </section>
    </div>

    <v-dialog v-model="confirmRestore" max-width="460">
      <v-card class="pa-5">
        <div class="text-h6 font-weight-bold mb-2">
          Restore {{ sectionLabel }} to v{{ selectedVersion?.version_no }}?
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          The current content will be replaced with this version's content.
          A new <code>revert</code> entry is added so today's version is NOT
          destroyed — you can switch back to it from this drawer later.
        </p>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmRestore = false">Cancel</v-btn>
          <v-btn color="warning" variant="flat" :loading="restoring" @click="doRestore">
            Restore
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="2500"
      location="bottom"
    >
      {{ snackbar.text }}
    </v-snackbar>
  </AppSideSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import api from '@/services/api'
import AppSideSheet from '@/components/common/AppSideSheet.vue'
import DiffView from '@/components/common/DiffView.vue'
import VersionRail, { type VersionRailItem } from '@/components/common/VersionRail.vue'
import type { BUDDesign } from '@/types'
import { relativeTime } from '@/utils/date'
import { diffStats as statsOf, lineDiff } from '@/utils/lineDiff'

interface BUDVersionSummary {
  id: string
  phase: string
  version_no: number
  source: 'ui' | 'mcp' | 'agent' | 'migration' | 'revert'
  edited_by: string | null
  mcp_token_id: string | null
  reason: string | null
  edited_at: string
}

interface BUDVersionDetail extends BUDVersionSummary {
  // Snapshot is a JSONB blob; the keys we care about per phase are
  // resolved through ``snapshotKey`` below. Other keys exist (title,
  // assignee_id, etc.) but the diff viewer is scoped to the active
  // section's content field — cross-phase audit lives in the header
  // History dialog.
  snapshot: Record<string, unknown>
}

interface Props {
  modelValue: boolean
  budId: string
  budStatus: string
  // The active section the toolbar was clicked from. We translate this
  // to a (phase, snapshot key) pair locally — kept here rather than
  // passed in so adding a new section only touches this component.
  section: 'requirements' | 'tech-spec' | 'design' | 'testing' | 'code-review'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  reverted: []
}>()

// Two-way bind via the side sheet's v-model.
const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// Section → (phase, snapshot key). DESIGN snaps under the sentinel
// ``__design_html`` because design content lives in bud_designs, not
// bud_documents — see backend/app/repositories/bud_version.py.
const SECTION_MAP: Record<
  Props['section'],
  { phase: string; label: string; field: string; format: 'markdown' | 'html' | 'json' }
> = {
  requirements: {
    phase: 'bud',
    label: 'Requirements',
    field: 'requirements_md',
    format: 'markdown',
  },
  'tech-spec': {
    phase: 'tech_arch',
    label: 'Tech Spec',
    field: 'tech_spec_md',
    format: 'markdown',
  },
  design: { phase: 'design', label: 'Design', field: '__design_html', format: 'html' },
  testing: { phase: 'testing', label: 'Test Plan', field: 'test_plan_md', format: 'markdown' },
  'code-review': {
    phase: 'code_review',
    label: 'Code Review',
    field: 'code_review_comments',
    format: 'json',
  },
}

const sectionConfig = computed(() => SECTION_MAP[props.section])
const phase = computed(() => sectionConfig.value.phase)
const sectionLabel = computed(() => sectionConfig.value.label)

const versions = ref<BUDVersionSummary[]>([])
const loading = ref(false)
const selectedVersion = ref<BUDVersionDetail | null>(null)
const loadingDetail = ref(false)
const currentContent = ref<string>('')

const restoring = ref(false)
const confirmRestore = ref(false)

const snackbar = ref<{ show: boolean; text: string; color: 'success' | 'error' }>({
  show: false,
  text: '',
  color: 'success',
})

function notify(text: string, color: 'success' | 'error' = 'success'): void {
  snackbar.value = { show: true, text, color }
}

function sourceColor(source: BUDVersionSummary['source']): string {
  switch (source) {
    case 'ui':
      return 'primary'
    case 'mcp':
      return 'brand'
    case 'agent':
      return 'success'
    case 'migration':
      return 'muted'
    case 'revert':
      return 'warning'
  }
}

// Stringify the snapshot field for line-by-line diff. JSON arrays
// (code_review_comments) are pretty-printed so the diff is readable;
// markdown and HTML pass through verbatim.
function stringifyForDiff(value: unknown, format: 'markdown' | 'html' | 'json'): string {
  if (value == null) return ''
  if (format === 'json') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

const railItems = computed<VersionRailItem[]>(() =>
  versions.value.map(v => ({
    id: v.id,
    label: `v${v.version_no}`,
    at: v.edited_at,
    badge: { text: v.source, color: sourceColor(v.source) },
    note: v.reason,
  })),
)

function selectById(id: string): void {
  const v = versions.value.find(x => x.id === id)
  if (v) void selectVersion(v)
}

const oldText = computed(() => {
  if (!selectedVersion.value) return ''
  const cfg = sectionConfig.value
  return stringifyForDiff(selectedVersion.value.snapshot[cfg.field], cfg.format)
})

const diffStats = computed(() =>
  selectedVersion.value ? statsOf(lineDiff(oldText.value, currentContent.value)) : null,
)

const restoreDisabledReason = computed<string | null>(() => {
  if (props.budStatus === 'closed' || props.budStatus === 'discarded') {
    return 'Cannot restore on a closed or discarded BUD.'
  }
  if (selectedVersion.value?.source === 'migration') {
    return 'Backfill baseline — restoring would set the section to its initial state.'
  }
  return null
})

async function loadVersions(): Promise<void> {
  loading.value = true
  selectedVersion.value = null
  try {
    const { data } = await api.get<BUDVersionSummary[]>(
      `/v1/buds/${props.budId}/versions`,
      { params: { limit: 200 } },
    )
    versions.value = data.filter((v) => v.phase === phase.value)
  } catch (err) {
    notify(err instanceof Error ? err.message : 'Failed to load history', 'error')
  } finally {
    loading.value = false
  }
}

async function fetchCurrentContent(): Promise<void> {
  const cfg = sectionConfig.value
  try {
    if (cfg.format === 'html') {
      // Design content lives in bud_designs — pull the BUD-level row.
      // The endpoint responds with a bare array (``response_model=
      // list[BUDDesignRead]``), not an envelope; type it off the shared
      // BUDDesign so a backend shape change fails the build instead of
      // throwing at runtime.
      const { data } = await api.get<BUDDesign[]>(`/v1/buds/${props.budId}/designs`)
      const budLevel = data.find((d) => d.repo_id == null)
      currentContent.value = budLevel?.design_html ?? ''
    } else {
      const { data } = await api.get<Record<string, unknown>>(`/v1/buds/${props.budId}`)
      currentContent.value = stringifyForDiff(data[cfg.field], cfg.format)
    }
  } catch (err) {
    notify(err instanceof Error ? err.message : 'Failed to load current content', 'error')
    currentContent.value = ''
  }
}

async function selectVersion(v: BUDVersionSummary): Promise<void> {
  loadingDetail.value = true
  try {
    const { data } = await api.get<BUDVersionDetail>(
      `/v1/buds/${props.budId}/versions/${v.phase}/${v.version_no}`,
    )
    selectedVersion.value = data
  } catch (err) {
    notify(err instanceof Error ? err.message : 'Failed to load version', 'error')
  } finally {
    loadingDetail.value = false
  }
}

async function doRestore(): Promise<void> {
  if (!selectedVersion.value) return
  const target = selectedVersion.value
  restoring.value = true
  try {
    await api.post(`/v1/buds/${props.budId}/revert/${target.phase}/${target.version_no}`)
    notify(`Restored ${sectionLabel.value} to v${target.version_no}`)
    confirmRestore.value = false
    emit('reverted')
    // Refresh both the version list (a new revert row landed) and the
    // current content baseline (the diff against subsequent versions
    // now compares against the restored text).
    await Promise.all([loadVersions(), fetchCurrentContent()])
  } catch (err) {
    notify(err instanceof Error ? err.message : 'Restore failed', 'error')
  } finally {
    restoring.value = false
  }
}

// Reload everything whenever the drawer opens or the section the user
// clicked from changes (e.g. they close the drawer, switch tabs, then
// reopen).
watch(
  () => [props.modelValue, props.section],
  ([opened]) => {
    if (!opened) return
    void loadVersions()
    void fetchCurrentContent()
  },
  { immediate: true },
)
</script>

<style scoped>
.diff-drawer__scope {
  margin: 0 0 12px;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.diff-drawer__body {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: calc(100vh - 140px);
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  overflow: hidden;
}
@media (max-width: 760px) {
  .diff-drawer__body {
    grid-template-columns: minmax(0, 1fr);
    min-height: 0;
  }
  .diff-rail {
    max-height: 220px;
    border-right: 0;
    border-bottom: 1px solid rgb(var(--v-theme-rule));
  }
}
.diff-rail {
  border-right: 1px solid rgb(var(--v-theme-rule));
  overflow-y: auto;
  padding: 8px;
  background: rgba(var(--v-theme-on-surface), 0.02);
}

.diff-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.diff-pane__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  background: rgb(var(--v-theme-surface));
  flex-wrap: wrap;
}
.diff-pane__placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.diff-stats {
  display: inline-flex;
  gap: 8px;
  font-family: var(--v-font-family-monospace, 'Menlo', monospace);
  font-size: 12px;
  font-weight: 600;
}
.diff-stats__added {
  color: rgb(var(--v-theme-success));
}
.diff-stats__removed {
  color: rgb(var(--v-theme-error));
}
</style>
