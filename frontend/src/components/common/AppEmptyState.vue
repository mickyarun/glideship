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

<!-- An empty list or page: what's missing, what to do
     about it, and the buttons to do it. -->
<template>
  <div class="app-empty" role="status">
    <div class="app-empty__icon" aria-hidden="true">
      <v-icon :icon="icon" size="28" />
    </div>
    <div class="app-empty__title text-body-1">{{ title }}</div>
    <p v-if="body" class="app-empty__body text-body-2 text-medium-emphasis">{{ body }}</p>
    <div v-if="$slots.actions" class="app-empty__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ icon: string; title: string; body?: string }>()
</script>

<style scoped>
.app-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 16px;
}
.app-empty__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
  margin-bottom: 16px;
}
.app-empty__title {
  font-weight: 600;
}
.app-empty__body {
  max-width: 48ch;
  margin-top: 4px;
}
.app-empty__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
}
</style>
