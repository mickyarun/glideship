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

<!-- Add a card at the bottom of a column. Enter adds it and keeps the box
     open for the next one; Esc (or Cancel) closes it and puts focus back
     on "Add a card". Shift+Enter is a line break the title will trim. -->
<template>
  <div class="quick-add">
    <form v-if="open" class="quick-add__form" @submit.prevent="submit">
      <v-textarea
        ref="field"
        v-model="title"
        :aria-label="`New card title in ${stageName}`"
        placeholder="What needs doing?"
        rows="2"
        auto-grow
        hide-details="auto"
        density="compact"
        :maxlength="maxLength ?? undefined"
        :error-messages="error || undefined"
        :disabled="saving"
        @keydown.enter.exact.prevent="submit"
        @keydown.esc.prevent="close"
      />
      <div class="quick-add__actions">
        <v-btn type="submit" color="primary" size="small" :loading="saving" :disabled="!title.trim()">Add card</v-btn>
        <v-btn variant="text" size="small" @click="close">Cancel</v-btn>
      </div>
    </form>
    <v-btn
      v-else
      ref="opener"
      variant="text"
      size="small"
      prepend-icon="mdi-plus"
      class="quick-add__open"
      @click="show"
    >
      Add a card
    </v-btn>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  stageName: string
  /** From GET /boards/limits; null until it loads. */
  maxLength: number | null
  submitCard: (title: string) => Promise<string | null>
}>()

const open = defineModel<boolean>('open', { default: false })
const title = ref('')
const error = ref('')
const saving = ref(false)
const field = ref<{ focus: () => void } | null>(null)
const opener = ref<{ $el: HTMLElement } | null>(null)

// However it opens (the button here, or the board's "New card"), the
// title box takes focus.
watch(
  open,
  async isOpen => {
    if (!isOpen) return
    await nextTick()
    field.value?.focus()
  },
  { immediate: true },
)

function show(): void {
  open.value = true
}

async function close(): Promise<void> {
  open.value = false
  title.value = ''
  error.value = ''
  await nextTick()
  opener.value?.$el.focus()
}

async function submit(): Promise<void> {
  const text = title.value.trim()
  if (!text || saving.value) return
  saving.value = true
  error.value = (await props.submitCard(text)) ?? ''
  saving.value = false
  if (!error.value) title.value = ''
  await nextTick()
  field.value?.focus()
}
</script>

<style scoped>
.quick-add__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-add__actions {
  display: flex;
  gap: 6px;
}
.quick-add__open {
  width: 100%;
  justify-content: flex-start;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (pointer: coarse) {
  .quick-add__open {
    min-height: 44px;
  }
}
</style>
