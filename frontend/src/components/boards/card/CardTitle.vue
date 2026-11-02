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

<!-- A card's title as the page heading. Editors click it (the pencil sits
     right after the text, as on a BUD) to rename it in place: Enter or
     leaving the field saves, Escape cancels, and a refused save keeps the
     draft in the field. -->
<template>
  <div class="card-title">
    <h1 v-if="!editing" class="bud-header__title">
      <button v-if="editable" type="button" class="bud-header__title-btn" title="Rename" @click="start">
        {{ value }}<span class="d-sr-only">, rename</span>
        <v-icon icon="mdi-pencil-outline" size="18" class="bud-header__title-icon" aria-hidden="true" />
      </button>
      <template v-else>{{ value }}</template>
    </h1>
    <v-text-field
      v-else
      v-model="draft"
      label="Title"
      density="compact"
      autofocus
      hide-details
      :maxlength="maxLength ?? undefined"
      :loading="saving"
      class="bud-header__title-field"
      @blur="submit"
      @keyup.enter="submit"
      @keyup.escape="editing = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  value: string
  editable: boolean
  maxLength?: number | null
  save: (title: string) => Promise<boolean>
}>()

const editing = ref(false)
const saving = ref(false)
const draft = ref('')

function start(): void {
  draft.value = props.value
  editing.value = true
}

async function submit(): Promise<void> {
  const title = draft.value.trim()
  if (saving.value || !editing.value) return
  if (!title || title === props.value) {
    editing.value = false
    return
  }
  saving.value = true
  const ok = await props.save(title)
  saving.value = false
  if (ok) editing.value = false
}
</script>

<style scoped src="../../buds/detail/bud-header.css"></style>
