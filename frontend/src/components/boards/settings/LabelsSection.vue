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

<!-- Labels: the tags cards can carry on this board. Add, rename, recolour
     and delete; each change saves as it's made, and deleting asks first
     since cards carrying the label lose it. -->
<template>
  <AppPanel title="Labels" :note="plural(labels.labels.value.length, 'label')">
    <form v-if="!disabled" class="labels__add" aria-label="Add a label" @submit.prevent="add">
      <v-text-field
        ref="nameField"
        v-model="name"
        label="New label"
        :maxlength="nameMax ?? undefined"
        :error-messages="problem || undefined"
        density="compact"
        hide-details="auto"
      />
      <LabelColorSelect v-model="color" label="Colour" />
      <v-btn type="submit" variant="outlined" height="40" prepend-icon="mdi-plus" :loading="adding">Add label</v-btn>
    </form>
    <ul v-if="disabled && labels.labels.value.length" class="labels__tags" aria-label="Labels">
      <li v-for="label in labels.labels.value" :key="label.id">
        <AppTag :color="labelColor(label.color)">{{ label.name }}</AppTag>
      </li>
    </ul>
    <ul v-else-if="labels.labels.value.length" class="labels__list" aria-label="Labels">
      <LabelRow
        v-for="label in labels.labels.value"
        :key="label.id"
        :label="label"
        :name-max="nameMax"
        :disabled="disabled"
        :name-block="labels.nameBlock"
        @rename="next => labels.rename(label, next)"
        @recolor="next => labels.recolor(label, next)"
        @delete="askDelete(label)"
      />
    </ul>
    <AppEmptyState v-else icon="mdi-tag-outline" title="No labels yet" body="Labels let people sort and filter the cards on this board." />
    <AppConfirmDialog
      v-model="deleteOpen"
      :title="`Delete the ${deleting?.name ?? ''} label?`"
      body="Cards carrying it lose it. This can't be undone."
      action="Delete label"
      color="error"
      :busy="status.saving.value"
      @confirm="confirmDelete"
    />
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import LabelColorSelect from '@/components/boards/settings/LabelColorSelect.vue'
import LabelRow from '@/components/boards/settings/LabelRow.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useLabelSettings } from '@/composables/useLabelSettings'
import AppTag from '@/components/common/AppTag.vue'
import { LABEL_COLORS, labelColor } from '@/constants/boards'
import type { BoardLimits, LabelColor, LabelRead } from '@/types/boards'
import { plural } from '@/utils/format'

const props = defineProps<{ limits: BoardLimits | null; status: BoardSettingsStatus; disabled: boolean }>()

const labels = useLabelSettings(useBoardContext(), props.status)
const nameMax = computed(() => props.limits?.label_name_max ?? null)
const name = ref('')
const color = ref<LabelColor>(LABEL_COLORS[0])
const problem = ref('')
const adding = ref(false)
const nameField = ref<{ focus: () => void } | null>(null)
const deleting = ref<LabelRead | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: open => {
    if (!open) deleting.value = null
  },
})

async function add(): Promise<void> {
  problem.value = labels.nameBlock(name.value) ?? ''
  if (problem.value) return
  adding.value = true
  const ok = await labels.create(name.value, color.value)
  adding.value = false
  if (!ok) return
  name.value = ''
  await nextTick()
  nameField.value?.focus()
}

function askDelete(label: LabelRead): void {
  props.status.clearError()
  deleting.value = label
}

async function confirmDelete(): Promise<void> {
  const label = deleting.value
  deleting.value = null
  if (label) await labels.remove(label)
}
</script>

<style scoped>
.labels__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.labels__add {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px auto;
  gap: 12px;
  align-items: start;
}
.labels__list {
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}
@media (max-width: 600px) {
  .labels__add {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
