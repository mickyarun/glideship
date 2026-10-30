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

<!-- A card's description: markdown, rendered and sanitised by renderMarkdown, with Edit for
     editors. The editor stays open with the draft until the save lands. -->
<template>
  <AppPanel title="Description">
    <template v-if="editable && !md.editing.value" #action>
      <v-btn variant="text" size="small" prepend-icon="mdi-pencil-outline" @click="md.toggle()">Edit</v-btn>
    </template>
    <template v-if="md.editing.value">
      <v-textarea
        v-model="md.editValue.value"
        label="Description (markdown)"
        variant="outlined"
        rows="6"
        auto-grow
        autofocus
        :counter="maxLength ?? undefined"
        :maxlength="maxLength ?? undefined"
      />
      <div class="card-text__actions">
        <v-btn variant="text" size="small" @click="md.editing.value = false">Cancel</v-btn>
        <v-btn variant="flat" color="primary" size="small" :loading="saving" @click="commit">Save</v-btn>
      </div>
    </template>
    <div v-else-if="value" class="markdown-body" v-html="html" />
    <p v-else class="card-text__empty">{{ editable ? 'No description yet. Use Edit to add one.' : 'No description.' }}</p>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useMarkdownSection } from '@/composables/useMarkdownSection'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  value: string | null
  editable: boolean
  maxLength: number | null
  save: (value: string) => Promise<boolean>
}>()

const md = useMarkdownSection(() => props.value ?? '', props.save)
const saving = ref(false)
const html = computed(() => renderMarkdown(props.value))

async function commit(): Promise<void> {
  saving.value = true
  await md.save()
  saving.value = false
}
</script>

<style scoped>
.card-text__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.card-text__empty {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
