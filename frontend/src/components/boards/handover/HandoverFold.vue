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

<!-- A folded section of the handover dialog: a bordered box whose summary
     line names it and says what's inside ("What the BUD gets · …",
     "Agents · 4 on, default skills"), opening to its content. A plain
     details element, so the keyboard and screen readers know it. -->
<template>
  <details class="handover-fold" :open="open" @toggle="open = ($event.target as HTMLDetailsElement).open">
    <summary class="handover-fold__summary">
      {{ title }} <span class="handover-fold__meta">· {{ meta }}</span>
    </summary>
    <div class="handover-fold__body"><slot /></div>
  </details>
</template>

<script setup lang="ts">
defineProps<{ title: string; meta: string }>()
const open = defineModel<boolean>('open', { default: false })
</script>

<style scoped>
.handover-fold {
  padding: 12px 14px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: var(--radius-card);
  background: rgb(var(--v-theme-background));
}
.handover-fold__summary {
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}
.handover-fold__meta {
  font-size: 12px;
  font-weight: 400;
  color: rgb(var(--v-theme-on-surface-variant));
}
.handover-fold__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}
</style>
