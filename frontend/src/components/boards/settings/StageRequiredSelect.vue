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
     may enter, picked as chips. Saves on each change, in the server's
     order. -->
<template>
  <v-select
    :model-value="modelValue"
    :items="items"
    :aria-label="`Required to enter ${stageName}`"
    label="Required to enter"
    placeholder="Nothing"
    persistent-placeholder
    multiple
    chips
    closable-chips
    density="compact"
    hide-details
    @update:model-value="(next: StageRequiredField[]) => emit('update:modelValue', inOrder(next))"
  />
</template>

<script setup lang="ts">
import type { StageRequiredField } from '@/types/boards'
import { fieldName, inOrder, REQUIRED_FIELDS } from '@/utils/stageRules'

defineProps<{ modelValue: StageRequiredField[]; stageName: string }>()
const emit = defineEmits<{ 'update:modelValue': [fields: StageRequiredField[]] }>()

const items = REQUIRED_FIELDS.map(f => ({ title: fieldName(f), value: f }))
</script>
