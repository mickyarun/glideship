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

<!-- One label in the settings list: how it looks on a card, its name (saved
     when the field is left or Enter is pressed), its colour and delete. -->
<template>
  <li class="label-row">
    <AppTag :color="labelColor(label.color)" class="label-row__preview">{{ label.name }}</AppTag>
    <v-text-field
      v-model="name"
      :aria-label="`Name of the ${label.name} label`"
      :maxlength="nameMax ?? undefined"
      :disabled="disabled"
      :error-messages="problem || undefined"
      density="compact"
      hide-details="auto"
      @blur="commit"
      @keydown.enter.prevent="($event.target as HTMLElement).blur()"
      @keydown.esc="name = label.name"
    />
    <LabelColorSelect
      :model-value="label.color"
      :aria-label="`Colour of the ${label.name} label`"
      :disabled="disabled"
      @update:model-value="emit('recolor', $event)"
    />
    <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="disabled" :aria-label="`Delete the ${label.name} label`" @click="emit('delete')" />
  </li>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import LabelColorSelect from '@/components/boards/settings/LabelColorSelect.vue'
import AppTag from '@/components/common/AppTag.vue'
import { labelColor } from '@/constants/boards'
import type { LabelColor, LabelRead } from '@/types/boards'

const props = defineProps<{
  label: LabelRead
  nameMax: number | null
  disabled: boolean
  nameBlock: (name: string, exceptId: string) => string | null
}>()
const emit = defineEmits<{ rename: [name: string]; recolor: [color: LabelColor]; delete: [] }>()

const name = ref(props.label.name)
const problem = ref('')
watch(() => props.label.name, next => (name.value = next))

function commit(): void {
  if (name.value.trim() === props.label.name) {
    problem.value = ''
    return
  }
  problem.value = props.nameBlock(name.value, props.label.id) ?? ''
  if (!problem.value) emit('rename', name.value.trim())
}
</script>

<style scoped>
.label-row {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr) 160px auto;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.label-row__preview {
  justify-self: start;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 600px) {
  .label-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .label-row__preview {
    grid-column: 1 / -1;
  }
}
</style>
