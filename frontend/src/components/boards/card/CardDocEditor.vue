<!--
 * Copyright 2025-2026 Arun Rajkumar
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 -->

<!-- One card document, read rendered or edited as markdown with the BUD
     section toolbar (Edit / Preview, Export, Import). Saving writes a new
     version on top of the one the edit started from; if someone saved a
     newer one meanwhile, a note offers to compare or save mine anyway, and
     the draft stays. ``seed`` opens it already editing that text (an edit
     kept from an AI draft that went). Viewers read it with no toolbar.
     The ``empty`` slot replaces the not-written-yet line. -->
<template>
  <AppPanel :title="label" :note="doc ? `Version ${doc.version}` : 'Not written yet'">
    <template v-if="canEdit" #action>
      <BUDSectionToolbar
        :is-editing="md.editing.value"
        :agent-locked="saving"
        active-tab="document"
        :current-section="kind"
        @toggle-edit="md.toggle()"
        @export-section="exportDoc"
        @import-section="(_, file) => importDoc(file)"
      />
    </template>
    <template v-if="md.editing.value">
      <CardDocConflictNote
        v-if="conflict && theirs !== null"
        class="mb-3"
        :version="theirs"
        :comparing="comparing"
        :saving="saving"
        @compare="comparing = !comparing"
        @save="saveMine"
      />
      <DiffView
        v-if="conflict && comparing"
        class="mb-3"
        :old="doc?.body_md ?? ''"
        :new="md.editValue.value"
        :label="`Their ${DOC_NAMES[kind]} compared with your draft`"
      />
      <v-textarea
        v-model="md.editValue.value"
        :label="`${label} (markdown)`"
        variant="outlined"
        rows="12"
        auto-grow
        autofocus
        :counter="maxLength ?? undefined"
        :maxlength="maxLength ?? undefined"
      />
      <div class="doc-editor__actions">
        <v-btn variant="text" size="small" @click="cancel">Cancel</v-btn>
        <v-btn variant="flat" color="primary" size="small" :loading="saving" @click="commit">Save version</v-btn>
      </div>
    </template>
    <div v-else-if="doc?.body_md" class="markdown-body" v-html="html" />
    <slot v-else name="empty" :start="md.toggle">
      <p class="doc-editor__empty">No {{ DOC_NAMES[kind] }} yet.{{ canEdit ? ' Use Edit to write one.' : '' }}</p>
    </slot>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import CardDocConflictNote from '@/components/boards/card/CardDocConflictNote.vue'
import BUDSectionToolbar from '@/components/buds/BUDSectionToolbar.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import DiffView from '@/components/common/DiffView.vue'
import { useMarkdownSection } from '@/composables/useMarkdownSection'
import { DOC_LABELS, DOC_NAMES } from '@/constants/boards'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind, DocRead } from '@/types/boards'
import { saveBlob } from '@/utils/download'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  kind: CardDocKind
  doc: DocRead | undefined
  cardKey: string
  canEdit: boolean
  maxLength: number | null
  /** Asks before an open draft is thrown away; resolves true to go ahead. */
  confirmDiscard: () => Promise<boolean>
  /** Open already editing this text. */
  seed?: string | null
}>()
const emit = defineEmits<{
  result: [error: string | null, success: string]
  /** What has unsaved changes ("the PRD"), or null once nothing does. */
  dirty: [what: string | null]
}>()

const docs = useBoardCardDocsStore()
const saving = ref(false)
const comparing = ref(false)
const label = computed(() => DOC_LABELS[props.kind])
const html = computed(() => renderMarkdown(props.doc?.body_md))
/** The version the open edit started from. */
const base = ref<number | null>(null)
const theirs = computed(() => props.doc?.version ?? null)

const md = useMarkdownSection(
  () => props.doc?.body_md ?? '',
  async value => {
    const result = await docs.save(props.kind, value, base.value)
    // A conflict shows the note in the editor instead of an error.
    if (result.conflict) return false
    if (!result.error) base.value = theirs.value
    emit('result', result.error, `Saved the ${DOC_NAMES[props.kind]} as version ${docs.current[props.kind]?.version ?? ''}`)
    return !result.error
  },
)

const conflict = computed(() => md.editing.value && theirs.value !== base.value)
const dirty = computed(() => md.editing.value && md.editValue.value !== (props.doc?.body_md ?? ''))

watch(() => md.editing.value, open => {
  if (!open) return
  base.value = theirs.value
  comparing.value = false
})
watch(dirty, isDirty => emit('dirty', isDirty ? `the ${DOC_NAMES[props.kind]}` : null), { immediate: true })
onBeforeUnmount(() => emit('dirty', null))
onMounted(() => {
  if (!props.seed || !props.canEdit) return
  md.toggle()
  md.editValue.value = props.seed
})

async function commit(): Promise<void> {
  saving.value = true
  await md.save()
  saving.value = false
}

/** Save my draft on top of their newer version. */
function saveMine(): Promise<void> {
  base.value = theirs.value
  return commit()
}

function cancel(): void {
  md.editing.value = false
}

function exportDoc(): void {
  const name = `${props.cardKey}-${props.kind.replace('_', '-')}.md`
  saveBlob(new Blob([props.doc?.body_md ?? ''], { type: 'text/markdown' }), name)
}

/** Load a file's text into the editor to review before saving, asking first over a draft. */
async function importDoc(file: File): Promise<void> {
  if (dirty.value && !(await props.confirmDiscard())) return
  const text = await file.text()
  if (!md.editing.value) md.toggle()
  md.editValue.value = props.maxLength ? text.slice(0, props.maxLength) : text
}
</script>

<style scoped>
.doc-editor__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.doc-editor__empty {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
