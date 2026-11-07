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

<!-- One group of people HR should look at before opening a cycle. -->
<template>
  <div class="ready-list">
    <h3 class="ready-list__title">{{ title }} ({{ people.length }})</h3>
    <p class="ready-list__hint">{{ hint }}</p>
    <ul class="ready-list__people">
      <li v-for="(person, i) in people" :key="i">{{ person }}</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; hint: string; people: string[] }>()
</script>

<style scoped>
.ready-list__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.ready-list__hint {
  margin: 2px 0 4px;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.ready-list__people {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
}
</style>
