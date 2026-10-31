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

<!-- What the BUD's requirements will say: the card's PRD (or description)
     and its "From the board" section, rendered (sanitised by
     renderMarkdown), with Edit to change them for this handover only. The
     card keeps its own text. Folded by default, so the dialog stays short. -->
<template>
  <details class="handover-req" :open="expanded" @toggle="expanded = ($event.target as HTMLDetailsElement).open">
    <summary class="handover-req__summary">
      What the BUD gets <span class="handover-req__meta">· {{ source }}</span>
    </summary>
    <div class="handover-req__body">
      <div class="handover-req__bar">
        <AppPillToggle v-model="view" :options="VIEWS" size="sm" aria-label="Requirements view" />
        <span v-if="edited" class="handover-req__meta">Edited for this handover</span>
      </div>
      <v-textarea
        v-if="editing"
        v-model="text"
        label="Requirements (markdown)"
        rows="10"
        auto-grow
        :counter="maxLength ?? undefined"
        :maxlength="maxLength ?? undefined"
        hide-details="auto"
      />
      <div v-else-if="text.trim()" class="markdown-body handover-req__preview" v-html="html" />
      <p v-else class="handover-req__meta">Nothing yet: the card has no PRD or description.</p>
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ original: string; hasPrd: boolean; maxLength: number | null }>()
const text = defineModel<string>({ required: true })

type View = 'preview' | 'edit'
const VIEWS: { label: string; value: View }[] = [
  { label: 'Preview', value: 'preview' },
  { label: 'Edit', value: 'edit' },
]
const view = ref<View>('preview')
const editing = computed(() => view.value === 'edit')
const expanded = ref(false)
// Picking a view means I'm looking at it.
watch(view, () => (expanded.value = true))
const edited = computed(() => text.value !== props.original)
const source = computed(() => (props.hasPrd ? 'requirements from the PRD, plus what the board adds' : 'requirements from the description, plus what the board adds'))
const html = computed(() => renderMarkdown(text.value))
</script>

<style scoped>
.handover-req {
  padding: 12px 14px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  background: rgb(var(--v-theme-background));
}
.handover-req__summary {
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}
.handover-req__meta {
  font-size: 12px;
  font-weight: 400;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-req__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}
.handover-req__bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.handover-req__preview {
  max-height: 320px;
  overflow: auto;
  font-size: 14px;
}
</style>
