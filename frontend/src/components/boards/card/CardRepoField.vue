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

<!-- A card's repository in its details: the name (a link to its page when
     it has one), or None, and for editors a Change menu of the board's
     linked repositories with "No repository" to clear it. A repository the
     board no longer links reads as None. -->
<template>
  <span class="repo-field">
    <a v-if="repo?.url" :href="repo.url" target="_blank" rel="noopener noreferrer" class="repo-field__name">{{ repo.name }}</a>
    <span v-else-if="repo" class="repo-field__name">{{ repo.name }}</span>
    <span v-else class="repo-field__muted">None</span>
  </span>
  <v-menu v-if="editable" location="bottom end">
    <template #activator="{ props: menuProps }">
      <button v-bind="menuProps" type="button" class="repo-field__link" aria-label="Change repository">Change</button>
    </template>
    <v-list density="compact" min-width="220" max-height="320" aria-label="Repository">
      <v-list-item v-if="!repos.length" title="This board links no repositories yet" disabled />
      <template v-else>
        <v-list-item
          v-for="r in repos"
          :key="r.id"
          :title="r.name"
          :active="r.id === repoId"
          prepend-icon="mdi-source-repository"
          @click="emit('change', r.id)"
        />
        <v-divider class="my-1" />
        <v-list-item title="No repository" :disabled="!repoId" @click="emit('change', null)" />
      </template>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BoardRepoRead } from '@/types/boards'

const props = defineProps<{ repoId: string | null; repos: BoardRepoRead[]; editable: boolean }>()
const emit = defineEmits<{ change: [repoId: string | null] }>()

const repo = computed(() => props.repos.find(r => r.id === props.repoId) ?? null)
</script>

<style scoped>
.repo-field {
  min-width: 0;
  overflow-wrap: anywhere;
}
.repo-field__name {
  font-family: var(--font-mono);
  font-size: 13px;
  color: inherit;
}
a.repo-field__name {
  color: var(--color-accent-text);
  text-decoration: none;
}
a.repo-field__name:hover {
  text-decoration: underline;
}
.repo-field__muted {
  color: rgb(var(--v-theme-on-surface-variant));
}
.repo-field__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--color-accent-text);
  cursor: pointer;
}
.repo-field__link:hover { text-decoration: underline; }
.repo-field__link:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
@media (pointer: coarse) {
  .repo-field__link { min-height: 44px; }
}
</style>
