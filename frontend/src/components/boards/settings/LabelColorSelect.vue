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

<!-- Pick a label colour from the theme's label hues, each shown as a tag. -->
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
      <AppTag :color="labelColor(item.value as LabelColor)">{{ item.title }}</AppTag>
    </template>
    <template #item="{ item, props: itemProps }">
      <v-list-item v-bind="itemProps" :title="undefined">
        <AppTag :color="labelColor(item.value as LabelColor)">{{ item.title }}</AppTag>
      </v-list-item>
    </template>
  </v-select>
</template>

<script setup lang="ts">
import AppTag from '@/components/common/AppTag.vue'
import { LABEL_COLORS, labelColor } from '@/constants/boards'
import type { LabelColor } from '@/types/boards'

withDefaults(defineProps<{ label?: string; ariaLabel?: string; disabled?: boolean }>(), {
  label: undefined,
  ariaLabel: undefined,
  disabled: false,
})
const model = defineModel<LabelColor>({ required: true })

const items = LABEL_COLORS.map(value => ({ value, title: value[0].toUpperCase() + value.slice(1) }))
</script>
