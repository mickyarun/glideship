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
     open for the next one, even while the last is still saving (titles
     queue up in order); Esc (or Cancel) closes it and puts focus back on
     "Add a card". Shift+Enter is a line break the title will trim. A stage
     with "Required to enter" fields asks for them under the title (and
     keeps them for the next card, all but the description); one that
     needs a PRD says new cards start elsewhere. -->
<template>
  <div class="quick-add">
    <p v-if="createBlock" class="quick-add__note">{{ createBlock }}</p>
    <form v-else-if="open" class="quick-add__form" @submit.prevent="submit">
      <v-textarea
        ref="field"
        v-model="title"
        label="New card title"
        rows="2"
        auto-grow
        density="compact"
        hint="Enter adds and keeps this open · Esc closes"
        persistent-hint
        :maxlength="maxLength ?? undefined"
        :error-messages="error || undefined"
        @keydown.enter.exact.prevent="submit"
        @keydown.esc.prevent="close"
      />
      <QuickAddRequired v-if="fields.length" v-model="extras" :stage-name="stageName" :fields="fields" />
      <p class="quick-add__status" role="status">{{ notice }}</p>
      <div class="quick-add__actions">
        <v-btn type="submit" color="primary" size="small" :loading="queued > 0" :disabled="!title.trim() || missing.length > 0">
          Add card
        </v-btn>
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
      @click="open = true"
    >
      Add a card
    </v-btn>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import QuickAddRequired from '@/components/boards/board/QuickAddRequired.vue'
import type { ActionResult } from '@/stores/boardCardActions'
import type { CardCreateExtras, StageRequiredField } from '@/types/boards'
import { inOrder, missingFor, needsList, newCardFacts, NOT_ON_CREATE } from '@/utils/stageRules'

const props = withDefaults(defineProps<{
  stageName: string
  /** From GET /boards/limits; null until it loads. */
  maxLength: number | null
  /** The stage's "Required to enter" fields. */
  required?: StageRequiredField[]
  submitCard: (title: string, extras: CardCreateExtras) => Promise<ActionResult>
}>(), { required: () => [] })

const open = defineModel<boolean>('open', { default: false })
const title = ref('')
const error = ref('')
const notice = ref('')
const queued = ref(0)
const extras = ref<CardCreateExtras>({})
const fields = computed(() => inOrder(props.required))
const missing = computed(() => missingFor(newCardFacts(extras.value), { required_fields: fields.value }))
const createBlock = computed(() => {
  const never = fields.value.filter(f => NOT_ON_CREATE.has(f))
  return never.length
    ? `${props.stageName} needs ${needsList(never)}, so new cards start in another stage and move here once they have one.`
    : null
})
const field = ref<{ focus: () => void } | null>(null)
const opener = ref<{ $el: HTMLElement } | null>(null)
// Saves run one after another, so cards land in the order they were typed.
let chain: Promise<void> = Promise.resolve()

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

async function close(): Promise<void> {
  open.value = false
  title.value = ''
  error.value = ''
  notice.value = ''
  extras.value = {}
  await nextTick()
  opener.value?.$el.focus()
}

function submit(): void {
  const text = title.value.trim()
  if (!text || missing.value.length) return
  const sent = { ...extras.value }
  extras.value = { ...sent, description_md: null }
  title.value = ''
  error.value = ''
  queued.value++
  chain = chain.then(async () => {
    const result = await props.submitCard(text, sent)
    queued.value--
    if (result.error) {
      error.value = result.error
      // Give the title back unless something new is already typed.
      if (!title.value) title.value = text
      if (!extras.value.description_md) extras.value = { ...extras.value, description_md: sent.description_md ?? null }
    } else {
      notice.value = result.shown
        ? `Added "${text}".`
        : `Added "${text}" to the bottom of ${props.stageName}.`
    }
  })
}
</script>

<style scoped>
.quick-add__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-add__status {
  margin: 0;
  min-height: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.quick-add__note {
  margin: 0;
  padding: 4px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
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
