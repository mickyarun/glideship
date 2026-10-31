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

<!-- The target stage in "Move to another board". A stage the arriving
     card can't enter yet wears a lock and says what it needs, as in the
     card's menu; ``note`` says why the preselected stage isn't the one the
     server would pick. -->
<template>
  <v-select
    :model-value="modelValue"
    :menu="menu"
    :items="stages"
    item-title="name"
    item-value="id"
    label="Stage"
    :loading="loading"
    hide-details
    @update:model-value="emit('update:modelValue', $event)"
    @update:menu="emit('update:menu', $event)"
  >
    <template #item="{ props: itemProps, item }">
      <v-list-item v-bind="itemProps" :subtitle="item.raw.reason">
        <template v-if="item.raw.reason" #append>
          <v-icon icon="mdi-lock-outline" size="16" aria-hidden="true" />
        </template>
      </v-list-item>
    </template>
  </v-select>
  <AppCallout v-if="note" variant="info" icon="mdi-information-outline">{{ note }}</AppCallout>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import type { MoveStageItem } from '@/utils/boardMoveStages'

defineProps<{
  modelValue: string | null
  menu: boolean
  stages: MoveStageItem[]
  loading: boolean
  note: string | null
}>()
const emit = defineEmits<{ 'update:modelValue': [id: string | null]; 'update:menu': [open: boolean] }>()
</script>
