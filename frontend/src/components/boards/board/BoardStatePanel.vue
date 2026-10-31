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
     centred in a panel. -->
<template>
  <section class="state-panel" :aria-label="title">
    <AppEmptyState icon="mdi-view-column-outline" :title="title" :body="body">
      <template v-if="$slots.default" #actions><slot /></template>
    </AppEmptyState>
  </section>
</template>

<script setup lang="ts">
import AppEmptyState from '@/components/common/AppEmptyState.vue'

defineProps<{ title: string; body: string }>()
</script>

<style scoped>
.state-panel {
  border-radius: 12px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
</style>
