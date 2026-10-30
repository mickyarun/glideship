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

<!-- An old version of a card document against the current text, line by
     line, with Restore (behind a confirmation) for editors. Restoring
     makes the old text current as a new version, so nothing is lost. -->
<template>
  <section class="doc-compare" :aria-label="`${label} v${version.version} compared with the current version`">
    <header class="doc-compare__head">
      <span>
        Comparing <strong>v{{ version.version }}</strong> → <strong>current (v{{ currentVersion }})</strong>
      </span>
      <span v-if="stats" class="doc-compare__stats">{{ stats.added }} added · {{ stats.removed }} removed</span>
      <v-spacer />
      <v-btn variant="text" size="small" @click="emit('close')">Back to the document</v-btn>
      <v-btn v-if="canEdit" size="small" color="warning" variant="flat" prepend-icon="mdi-undo" @click="confirming = true">
        Restore v{{ version.version }}
      </v-btn>
    </header>
    <div v-if="oldText === null" class="doc-compare__loading"><v-progress-circular indeterminate size="24" /></div>
    <DiffView v-else :old="oldText" :new="currentText" :label="`${label} changes`" />

    <AppConfirmDialog
      v-model="confirming"
      :title="`Restore ${label} v${version.version}?`"
      body="Its text becomes the current version, as a new version. The text there now stays in the history."
      action="Restore"
      :busy="restoring"
      @confirm="restore"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import DiffView from '@/components/common/DiffView.vue'
import { DOC_LABELS } from '@/constants/boards'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind, DocVersionRead } from '@/types/boards'
import { diffStats, lineDiff } from '@/utils/lineDiff'

const props = defineProps<{
  kind: CardDocKind
  version: DocVersionRead
  currentText: string
  currentVersion: number | null
  canEdit: boolean
}>()
const emit = defineEmits<{ close: []; result: [error: string | null, success: string] }>()

const docs = useBoardCardDocsStore()
const label = computed(() => DOC_LABELS[props.kind])
const oldText = ref<string | null>(null)
const confirming = ref(false)
const restoring = ref(false)
const stats = computed(() => (oldText.value === null ? null : diffStats(lineDiff(oldText.value, props.currentText))))

watch(
  () => [props.kind, props.version.version] as const,
  async ([kind, version]) => {
    oldText.value = null
    const text = await docs.versionText(kind, version)
    if (props.kind === kind && props.version.version === version) oldText.value = text ?? ''
  },
  { immediate: true },
)

async function restore(): Promise<void> {
  restoring.value = true
  const from = props.version.version
  const error = await docs.restore(props.kind, from)
  restoring.value = false
  confirming.value = false
  emit('result', error, `Restored ${label.value} v${from} as the current version`)
  if (!error) emit('close')
}
</script>

<style scoped>
.doc-compare {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  overflow: hidden;
}
.doc-compare__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-rule));
  font-size: 13px;
}
.doc-compare__stats {
  color: rgb(var(--v-theme-on-surface-variant));
}
.doc-compare__loading {
  display: flex;
  justify-content: center;
  padding: 32px;
}
</style>
