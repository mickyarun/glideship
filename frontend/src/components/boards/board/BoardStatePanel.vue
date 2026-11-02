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
     nothing (what's set, and Clear filters). The app's empty state,
     centred in a panel. Above the columns it's a compact row, so the
     columns and their Add a card stay in view. -->
<template>
  <section class="state-panel" :class="{ 'state-panel--compact': compact }" :aria-label="title">
    <div v-if="compact" class="state-panel__row" role="status">
      <span class="state-panel__icon" aria-hidden="true"><v-icon icon="mdi-view-column-outline" size="20" /></span>
      <div class="state-panel__text">
        <p class="state-panel__title">{{ title }}</p>
        <p v-if="body" class="state-panel__body">{{ body }}</p>
      </div>
      <div v-if="$slots.default" class="state-panel__actions"><slot /></div>
    </div>
    <AppEmptyState v-else icon="mdi-view-column-outline" :title="title" :body="body">
      <template v-if="$slots.default" #actions><slot /></template>
    </AppEmptyState>
  </section>
</template>

<script setup lang="ts">
import AppEmptyState from '@/components/common/AppEmptyState.vue'

defineProps<{ title: string; body: string; compact?: boolean }>()
</script>

<style scoped>
.state-panel {
  border-radius: 12px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
.state-panel__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  padding: 16px 20px;
}
.state-panel__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
}
.state-panel__text {
  flex: 1 1 200px;
  min-width: 0;
}
.state-panel__title {
  margin: 0;
  font-weight: 600;
}
.state-panel__body {
  margin: 2px 0 0;
  font-size: var(--text-sm);
  color: rgb(var(--v-theme-on-surface-variant));
}
.state-panel__actions {
  display: flex;
  gap: 8px;
}
</style>
