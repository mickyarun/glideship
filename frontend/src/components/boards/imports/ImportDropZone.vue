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

<!-- Upload a Trello board export: drop the .json file here or choose it.
     The size cap comes from the server's limits; without one the line
     leaves the number out rather than guess. -->
<template>
  <div
    class="drop-zone"
    :class="{ 'drop-zone--over': over }"
    @dragover.prevent="over = !disabled"
    @dragleave="over = false"
    @drop.prevent="drop"
  >
    <h3 class="drop-zone__title">Upload an export</h3>
    <p class="drop-zone__text">
      In Trello: Menu → Print, export and share → Export as JSON. Drop the file here{{ maxMb ? ` (up to ${maxMb} MB)` : '' }}.
    </p>
    <v-btn
      variant="outlined"
      prepend-icon="mdi-file-upload-outline"
      class="drop-zone__pick"
      :loading="busy"
      :disabled="disabled"
      @click="input?.click()"
    >
      Choose file
    </v-btn>
    <input
      ref="input"
      type="file"
      accept=".json,application/json"
      class="d-sr-only"
      tabindex="-1"
      aria-label="Trello board export (.json)"
      @change="picked"
    >
    <p class="drop-zone__note">Works for anyone. Only the last 1,000 actions come with it; attachments as links.</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ maxMb: number | null; busy: boolean; disabled: boolean }>()
const emit = defineEmits<{ file: [file: File] }>()

const input = ref<HTMLInputElement | null>(null)
const over = ref(false)

function send(file: File | undefined | null): void {
  if (file && !props.disabled) emit('file', file)
}

function picked(event: Event): void {
  const target = event.target as HTMLInputElement
  send(target.files?.[0])
  // The same file again (after a fix) still fires a change.
  target.value = ''
}

function drop(event: DragEvent): void {
  over.value = false
  send(event.dataTransfer?.files?.[0])
}
</script>

<style scoped>
.drop-zone {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 10px;
  border: 1px dashed rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.06);
}
.drop-zone--over {
  background: rgba(var(--v-theme-primary), 0.14);
}
.drop-zone__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.drop-zone__text {
  margin: 0;
  font-size: 13px;
}
.drop-zone__pick {
  align-self: flex-start;
}
.drop-zone__note {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
