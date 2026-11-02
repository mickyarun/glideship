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

<!-- A "Change" link that opens a checklist menu of options (a board's
     members, its labels): each pick toggles at once and the menu stays
     open for the next. -->
<template>
  <v-menu location="bottom end" :close-on-content-click="false">
    <template #activator="{ props: menuProps }">
      <button v-bind="menuProps" type="button" class="pick-menu__link" :aria-label="`Change ${label}`">Change</button>
    </template>
    <v-list density="compact" min-width="220" max-height="320" :aria-label="label">
      <v-list-item v-if="!items.length" :title="emptyText" disabled />
      <v-list-item
        v-for="item in items"
        :key="item.id"
        role="menuitemcheckbox"
        :aria-checked="selected.includes(item.id)"
        @click="toggle(item.id)"
      >
        <template #prepend>
          <v-icon :icon="selected.includes(item.id) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'" size="18" class="mr-2" />
          <AppMonogram v-if="item.person" :name="item.title" :src="item.photo ?? null" :size="22" class="mr-2" />
          <span v-else-if="item.color" class="pick-menu__swatch mr-2" :style="{ background: `rgb(var(--v-theme-${item.color}))` }" />
        </template>
        <v-list-item-title>{{ item.title }}</v-list-item-title>
        <v-list-item-subtitle v-if="item.note">{{ item.note }}</v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script lang="ts">
export interface PickItem {
  id: string
  title: string
  /** A person: shown with their photo or initials. */
  person?: boolean
  photo?: string | null
  /** A theme colour name for a swatch (labels). */
  color?: string
  /** A quiet second line ("via a team"). */
  note?: string | null
}
</script>

<script setup lang="ts">
import AppMonogram from '@/components/common/AppMonogram.vue'

const props = defineProps<{ items: PickItem[]; selected: string[]; label: string; emptyText: string }>()
const emit = defineEmits<{ change: [ids: string[]] }>()

function toggle(id: string): void {
  emit('change', props.selected.includes(id) ? props.selected.filter(s => s !== id) : [...props.selected, id])
}
</script>

<style scoped>
.pick-menu__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--color-accent-text);
  cursor: pointer;
}
.pick-menu__link:hover {
  text-decoration: underline;
}
.pick-menu__link:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.pick-menu__swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
@media (pointer: coarse) {
  .pick-menu__link {
    min-height: 44px;
  }
}
</style>
