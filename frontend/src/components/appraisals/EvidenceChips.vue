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

<!-- Examples already picked, as chips with a remove button: what is sent
     back to the server is always what the person can see here. -->
<template>
  <div v-if="modelValue.length" class="chips">
    <span class="chips__label">{{ label }}</span>
    <span v-for="id in modelValue" :key="id" class="chips__chip">
      {{ labels[id] ?? 'An example no longer in this period' }}
      <button type="button" class="chips__remove" :aria-label="`Remove ${labels[id] ?? 'example'}`" @click="remove(id)">
        <v-icon icon="mdi-close" size="14" />
      </button>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EvidenceOption } from '@/types/appraisalReview'

const props = defineProps<{ options: EvidenceOption[]; label: string }>()
const modelValue = defineModel<string[]>({ required: true })
const labels = computed(() => Object.fromEntries(props.options.map(o => [o.id, o.label])))

function remove(id: string): void {
  modelValue.value = modelValue.value.filter(v => v !== id)
}
</script>

<style scoped>
.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.chips__label {
  color: rgb(var(--v-theme-on-surface-variant));
}
.chips__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-pill);
}
.chips__remove {
  display: inline-flex;
  padding: 2px;
  border-radius: var(--radius-pill);
  color: rgb(var(--v-theme-on-surface-variant));
}
.chips__remove:hover {
  color: rgb(var(--v-theme-on-surface));
}
.chips__remove:focus-visible {
  outline: 2px solid var(--color-focus);
}
</style>
