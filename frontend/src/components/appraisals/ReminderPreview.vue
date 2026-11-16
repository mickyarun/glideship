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

<!-- What the reminder schedule sends, worded as the Slack DMs will be:
     counts and dates only, never a report's name or a note. -->
<template>
  <section class="dm-preview" aria-label="Slack messages this sends">
    <h3 class="dm-preview__title">Slack messages for one feedback period</h3>
    <ol class="dm-preview__list">
      <li v-for="(row, i) in rows" :key="i" class="dm-preview__row">
        <span class="dm-preview__when">{{ row.when }} · {{ row.who }}</span>
        <span class="dm-preview__text">{{ row.text }}</span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import type { DmPreview } from '@/utils/appraisalSetup'

defineProps<{ rows: DmPreview[] }>()
</script>

<style scoped>
.dm-preview {
  padding: 12px 16px;
  border: 1px dashed rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.dm-preview__title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}
.dm-preview__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dm-preview__row {
  display: flex;
  flex-direction: column;
}
.dm-preview__when {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.dm-preview__text {
  font-size: 14px;
}
</style>
