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

<!-- Picking the BUD to link the card to: type a key, number or title to
     search open BUDs, then pick one from the list (a BUD this card already
     holds can't be picked). The list is a listbox of options, so it reads
     as one choice. -->
<template>
  <div class="link-picker">
    <v-text-field
      v-model="search.query.value"
      type="search"
      label="Search open BUDs by key or title"
      prepend-inner-icon="mdi-magnify"
      hide-details
      autofocus
    />
    <AppCallout v-if="search.error.value" variant="error" role="alert">
      {{ search.error.value }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="search.search()">Try again</v-btn>
      </template>
    </AppCallout>
    <v-progress-linear v-else-if="search.loading.value" indeterminate />
    <p v-else-if="!search.settled.value" class="link-picker__empty">Type a BUD's key, number or title.</p>
    <p v-else-if="!search.options.value.length" class="link-picker__empty">No open BUD matches that.</p>
    <div v-else role="listbox" aria-label="Matching BUDs" class="link-picker__list">
      <button
        v-for="opt in search.options.value"
        :key="opt.id"
        type="button"
        role="option"
        class="link-picker__option"
        :class="{ 'link-picker__option--picked': opt.id === picked }"
        :aria-selected="opt.id === picked"
        :aria-disabled="!!opt.blocked"
        :disabled="!!opt.blocked"
        @click="picked = opt.id"
      >
        <span class="link-picker__key">{{ opt.key }}</span>
        <span class="link-picker__title">{{ opt.title }}</span>
        <span class="link-picker__note">{{ opt.blocked ?? statusLabel(opt.status) }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import type { useOpenBudSearch } from '@/composables/useOpenBudSearch'
import { statusLabel } from '@/utils/handoverChips'

defineProps<{ search: ReturnType<typeof useOpenBudSearch> }>()
const picked = defineModel<string | null>({ required: true })
</script>

<style scoped>
.link-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.link-picker__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 300px;
  overflow: auto;
}
.link-picker__option {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.link-picker__option:disabled {
  opacity: 0.6;
  cursor: default;
}
.link-picker__option--picked {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
}
.link-picker__option:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.link-picker__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.link-picker__title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link-picker__note,
.link-picker__empty {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
