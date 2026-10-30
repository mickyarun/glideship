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

<!-- Board-wide states over the columns: a new board with no cards yet
     ("Ops is ready", with Add your first card), and filters that match
     nothing (what's set, and Clear filters). -->
<template>
  <section class="state-panel" :aria-label="title">
    <h2 class="state-panel__title">{{ title }}</h2>
    <p class="state-panel__body">{{ body }}</p>
    <div v-if="$slots.default" class="state-panel__actions"><slot /></div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title: string; body: string }>()
</script>

<style scoped>
.state-panel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 18px 20px;
  border-radius: 12px;
  border: 1px dashed rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
.state-panel__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.state-panel__body {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.state-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
</style>
