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
     version; the editor stays open with the draft until it lands. Viewers
     read it with no toolbar. -->
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
        <v-btn variant="text" size="small" @click="md.editing.value = false">Cancel</v-btn>
        <v-btn variant="flat" color="primary" size="small" :loading="saving" @click="commit">Save version</v-btn>
      </div>
    </template>
    <div v-else-if="doc?.body_md" class="markdown-body" v-html="html" />
    <p v-else class="doc-editor__empty">
      {{ canEdit ? `No ${label.toLowerCase()} yet. Use Edit to write one.` : `No ${label.toLowerCase()} yet.` }}
    </p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import BUDSectionToolbar from '@/components/buds/BUDSectionToolbar.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useMarkdownSection } from '@/composables/useMarkdownSection'
import { DOC_LABELS } from '@/constants/boards'
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
}>()
const emit = defineEmits<{ result: [error: string | null, success: string] }>()

const docs = useBoardCardDocsStore()
const saving = ref(false)
const label = computed(() => DOC_LABELS[props.kind])
const html = computed(() => renderMarkdown(props.doc?.body_md))

const md = useMarkdownSection(
  () => props.doc?.body_md ?? '',
  async value => {
    const error = await docs.save(props.kind, value)
    emit('result', error, `Saved ${label.value} version ${docs.current[props.kind]?.version ?? ''}`.trim())
    return !error
  },
)

async function commit(): Promise<void> {
  saving.value = true
  await md.save()
  saving.value = false
}

function exportDoc(): void {
  const name = `${props.cardKey}-${props.kind.replace('_', '-')}.md`
  saveBlob(new Blob([props.doc?.body_md ?? ''], { type: 'text/markdown' }), name)
}

/** Load a file's text into the editor, to review before saving. */
async function importDoc(file: File): Promise<void> {
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
