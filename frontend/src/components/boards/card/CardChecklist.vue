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

<!-- A card's checklist: done of total, its lines (grouped under their
     group names when they have them), and an add field for editors. Each
     result is reported to the page (``result``) for its live region or
     snackbar; a moved line keeps keyboard focus on its arrow. -->
<template>
  <AppPanel title="Checklist" :note="total ? `${list.done.value} of ${total} done` : undefined">
    <p v-if="list.error.value" class="check-list__note" role="alert">{{ list.error.value }}</p>
    <p v-else-if="!total && !list.loading.value" class="check-list__note">
      {{ editable ? 'No items yet. Add the first below.' : 'No checklist.' }}
    </p>
    <section v-for="group in groups" :key="group.name ?? ''" class="check-list__group">
      <h3 v-if="group.name" class="check-list__heading">{{ group.name }}</h3>
      <ul class="check-list__items">
        <CardChecklistRow
          v-for="(item, i) in group.items"
          :key="item.id"
          :item="item"
          :editable="editable"
          :first="i === 0"
          :last="i === group.items.length - 1"
          :max-text="maxText"
          @toggle="report(list.toggle(item), item.done ? `Unticked ${item.text}` : `Ticked ${item.text}`)"
          @edit="text => report(list.edit(item, text), 'Item saved')"
          @remove="report(list.remove(item), `Deleted ${item.text}`)"
          @move="delta => move(item, delta)"
        />
      </ul>
    </section>
    <form v-if="editable && !full" class="check-list__add" @submit.prevent="add">
      <v-text-field
        v-model="draft"
        label="Add an item"
        variant="outlined"
        density="compact"
        hide-details
        :maxlength="maxText ?? undefined"
      />
      <v-btn type="submit" variant="outlined" :loading="adding" :disabled="!draft.trim()">Add</v-btn>
    </form>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import CardChecklistRow from '@/components/boards/card/CardChecklistRow.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { useCardChecklist } from '@/composables/useCardChecklist'
import type { ChecklistItem } from '@/types/boards'

const props = defineProps<{
  list: ReturnType<typeof useCardChecklist>
  editable: boolean
  maxText: number | null
  maxItems: number | null
}>()
const emit = defineEmits<{ result: [error: string | null, success: string] }>()

const draft = ref('')
const adding = ref(false)
const total = computed(() => props.list.items.value.length)
const full = computed(() => props.maxItems !== null && total.value >= props.maxItems)

const groups = computed(() => {
  const byName = new Map<string | null, ChecklistItem[]>()
  for (const item of props.list.items.value) {
    byName.set(item.group_name, [...(byName.get(item.group_name) ?? []), item])
  }
  return [...byName].map(([name, items]) => ({ name, items }))
})

async function report(pending: Promise<string | null>, success: string): Promise<void> {
  emit('result', await pending, success)
}

async function add(): Promise<void> {
  const text = draft.value.trim()
  if (!text || adding.value) return
  adding.value = true
  const error = await props.list.add(text)
  adding.value = false
  if (!error) draft.value = ''
  emit('result', error, `Added ${text}`)
}

async function move(item: ChecklistItem, delta: -1 | 1): Promise<void> {
  await report(props.list.move(item, delta), `Moved ${item.text} ${delta < 0 ? 'up' : 'down'}`)
  await nextTick()
  const button = document.querySelector<HTMLElement>(
    `[data-checklist-item="${item.id}"] [data-move="${delta < 0 ? 'up' : 'down'}"]`,
  )
  // At the end of its group the arrow is disabled; keep focus on the line's other arrow.
  const other = document.querySelector<HTMLElement>(
    `[data-checklist-item="${item.id}"] [data-move="${delta < 0 ? 'down' : 'up'}"]`,
  )
  ;(button && !button.hasAttribute('disabled') ? button : other)?.focus()
}
</script>

<style scoped>
.check-list__note {
  margin: 0 0 8px;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.check-list__group + .check-list__group {
  margin-top: 12px;
}
.check-list__heading {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface-variant));
}
.check-list__items {
  list-style: none;
  margin: 0;
  padding: 0;
}
.check-list__add {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
</style>
