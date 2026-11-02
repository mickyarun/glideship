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

<!-- The new board's template, as cards that fill the row: each a real radio
     (arrow keys move between them), with the template's stages. -->
<template>
  <fieldset class="tpl">
    <legend class="tpl__legend">Template</legend>
    <div class="tpl__grid">
      <label v-for="t in templates" :key="t.id" class="tpl__card" :class="{ 'tpl__card--on': model === t.id }">
        <input v-model="model" type="radio" :name="name" :value="t.id" class="tpl__input" />
        <span class="tpl__name">{{ t.name }}</span>
        <span class="tpl__stages">{{ t.stages.length ? t.stages.map(s => s.name).join(' · ') : t.description }}</span>
      </label>
    </div>
  </fieldset>
</template>

<script setup lang="ts">
import { useId } from 'vue'
import type { BoardTemplate } from '@/types/boards'

defineProps<{ templates: BoardTemplate[] }>()
const model = defineModel<string>({ required: true })
const name = useId()
</script>

<style scoped>
.tpl {
  border: 0;
  margin: 0;
  padding: 0;
}
.tpl__legend {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
}
.tpl__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 8px;
}
.tpl__card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-background));
  cursor: pointer;
}
.tpl__card--on {
  border-color: rgb(var(--v-theme-primary));
  background: var(--color-accent-soft);
}
.tpl__card:has(.tpl__input:focus-visible) {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.tpl__input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.tpl__name {
  font-size: 14px;
  font-weight: 600;
}
.tpl__stages {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 600px) {
  .tpl__grid {
    grid-template-columns: 1fr;
  }
}
</style>
