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

<!-- Pick a stage category; each option shows in its category colour. -->
<template>
  <v-select
    v-model="model"
    :items="items"
    :label="label"
    :aria-label="ariaLabel"
    :disabled="disabled"
    density="compact"
    hide-details
  >
    <template #selection="{ item }">
      <AppTag :color="CATEGORY_COLORS[item.value as StageCategory]">{{ item.title }}</AppTag>
    </template>
    <template #item="{ item, props: itemProps }">
      <v-list-item v-bind="itemProps" :title="undefined">
        <AppTag :color="CATEGORY_COLORS[item.value as StageCategory]">{{ item.title }}</AppTag>
      </v-list-item>
    </template>
  </v-select>
</template>

<script setup lang="ts">
import AppTag from '@/components/common/AppTag.vue'
import { CATEGORY_COLORS, CATEGORY_LABELS, STAGE_CATEGORIES } from '@/constants/boards'
import type { StageCategory } from '@/types/boards'

withDefaults(defineProps<{ label?: string; ariaLabel?: string; disabled?: boolean }>(), {
  label: undefined,
  ariaLabel: undefined,
  disabled: false,
})
const model = defineModel<StageCategory>({ required: true })

const items = STAGE_CATEGORIES.map(value => ({ value, title: CATEGORY_LABELS[value] }))
</script>
