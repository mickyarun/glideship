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

<!-- A short "are you sure?" dialog: a title, one paragraph and the
     confirming action. The default slot can add content (a note field, an
     error callout) under the paragraph.

       <AppConfirmDialog v-model="open" title="Close this bug?" body="…" action="Close bug" @confirm="close" />

     It stays open while ``busy``; the parent closes it once the action
     has succeeded. It opens with focus on Cancel, the safe choice, and on
     closing gives focus back to whatever had it when it opened; when that
     is gone (a deleted row), to ``returnFocus`` (the next row, an add
     field). ``color`` is the action's: ``error`` for destructive ones.
     ``secondary`` adds a quieter third choice beside Cancel. -->
<template>
  <v-dialog
    :model-value="modelValue"
    max-width="460"
    :persistent="busy"
    @update:model-value="emit('update:modelValue', $event)"
    @after-enter="cancel?.$el.focus()"
  >
    <v-card color="surface" class="app-confirm">
      <h2 class="app-confirm__title">{{ title }}</h2>
      <p class="app-confirm__body"><slot name="body">{{ body }}</slot></p>
      <slot />
      <div class="app-confirm__actions">
        <v-btn v-if="secondary" variant="text" :disabled="busy" @click="emit('secondary')">{{ secondary }}</v-btn>
        <v-btn ref="cancel" variant="text" :disabled="busy" @click="emit('update:modelValue', false)">Cancel</v-btn>
        <v-btn :color="color" variant="flat" :loading="busy" @click="emit('confirm')">{{ action }}</v-btn>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    body?: string
    action: string
    busy?: boolean
    color?: 'primary' | 'error' | 'warning'
    /** Where focus goes on close when the element that opened it is gone. */
    returnFocus?: HTMLElement | null
    /** A third choice's label ("Open card"); emits ``secondary``. */
    secondary?: string
  }>(),
  { body: '', busy: false, color: 'primary', returnFocus: null, secondary: '' },
)
const emit = defineEmits<{ 'update:modelValue': [open: boolean]; confirm: []; secondary: [] }>()
const cancel = ref<{ $el: HTMLElement } | null>(null)
let opener: HTMLElement | null = null

watch(() => props.modelValue, async (open, was) => {
  if (open) {
    opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    return
  }
  if (!was) return
  // After the parent has redrawn (a deleted row is gone by then) and the
  // overlay has let go of focus.
  await nextTick()
  setTimeout(restoreFocus)
}, { immediate: true })

function restoreFocus(): void {
  if (!opener) return
  const target = opener.isConnected ? opener : props.returnFocus
  opener = null
  target?.focus()
}
</script>

<style scoped>
.app-confirm {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 24px;
}
.app-confirm__title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
}
.app-confirm__body {
  margin: 0;
  font-size: 14px;
  line-height: 21px;
  color: rgb(var(--v-theme-ink-2));
}
.app-confirm__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
