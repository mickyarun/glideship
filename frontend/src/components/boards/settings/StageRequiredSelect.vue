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

<!-- A stage's "Required to enter": the fields a card must have before it
     may enter. Until it has any, it's a "+ Required to enter" button, so
     a list of stages stays light; then a labelled picker with the fields
     as tags, the same as a category. Picks show at once and save once
     they settle (or the list closes), in the server's order, so quick
     picks send one change. The default stage can't need a PRD: a new card
     lands there before it can have one. -->
<template>
  <v-btn
    v-if="!draft.length && !editing"
    variant="text"
    size="small"
    prepend-icon="mdi-plus"
    class="required__add"
    @click="start"
  >
    Required to enter
  </v-btn>
  <div v-else class="required">
    <span class="required__label" aria-hidden="true">Required to enter</span>
    <v-select
      ref="select"
      v-model:menu="menu"
      :model-value="draft"
      :items="items"
      item-props="props"
      :aria-label="`Required to enter ${stageName}`"
      placeholder="Nothing"
      multiple
      density="compact"
      hide-details
      class="required__select"
      @update:model-value="pick"
    >
      <template #selection="{ item }">
        <AppTag class="required__tag">{{ item.title }}</AppTag>
      </template>
    </v-select>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import AppTag from '@/components/common/AppTag.vue'
import { REQUIRED_SAVE_DELAY_MS } from '@/constants/boards'
import type { StageRequiredField } from '@/types/boards'
import { fieldName, inOrder, NOT_ON_CREATE, REQUIRED_FIELDS } from '@/utils/stageRules'

const props = defineProps<{ modelValue: StageRequiredField[]; stageName: string; isDefault: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [fields: StageRequiredField[]] }>()

const NOT_ON_DEFAULT = "The default stage can't need a PRD"

const draft = ref<StageRequiredField[]>([...props.modelValue])
const menu = ref(false)
const editing = ref(false)
const select = ref<{ focus: () => void } | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined

const items = computed(() =>
  REQUIRED_FIELDS.map(f => {
    const blocked = props.isDefault && NOT_ON_CREATE.has(f) && !draft.value.includes(f)
    return { title: fieldName(f), value: f, props: { disabled: blocked, subtitle: blocked ? NOT_ON_DEFAULT : undefined } }
  }),
)

// The board's copy wins once it changes, unless a pick is still waiting to save.
watch(() => props.modelValue, next => {
  if (timer === undefined) draft.value = [...next]
})

function flush(): void {
  if (timer === undefined) return
  clearTimeout(timer)
  timer = undefined
  if (draft.value.join() !== props.modelValue.join()) emit('update:modelValue', draft.value)
}

function pick(next: StageRequiredField[]): void {
  // Still picking, even with nothing picked: the list stays until it closes.
  editing.value = true
  draft.value = inOrder(next)
  clearTimeout(timer)
  timer = setTimeout(flush, REQUIRED_SAVE_DELAY_MS)
}

async function start(): Promise<void> {
  editing.value = true
  await nextTick()
  select.value?.focus()
  menu.value = true
}

// Closing the list saves what's picked; an empty list goes back to the button.
watch(menu, open => {
  if (open) {
    editing.value = true
    return
  }
  flush()
  editing.value = false
}, { flush: 'sync' })

onBeforeUnmount(flush)
</script>

<style scoped>
.required {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.required__label {
  flex: 0 0 auto;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.required__select {
  flex: 1 1 auto;
  min-width: 0;
}
.required__tag {
  margin: 2px 4px 2px 0;
}
.required__add {
  color: rgb(var(--v-theme-on-surface-variant));
}
/* A narrow list: the label sits above, as every other field's does. */
@container stages (max-width: 650px) {
  .required {
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
  }
}
@media (pointer: coarse) {
  .required__add {
    min-height: 44px;
  }
}
</style>
