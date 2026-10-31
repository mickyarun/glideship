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

<!-- Repositories: the tracked repositories this board's work lands in, so
     a card can name one and the board can be filtered by it. Admins link
     one from the org's active repositories (already linked ones show but
     can't be picked again) and unlink, which asks first since the cards
     naming it lose it. Everyone else reads the list. -->
<template>
  <AppPanel title="Repositories" :note="plural(repos.linked.value.length, 'linked repository', 'linked repositories')">
    <form v-if="!disabled" class="repos__add" aria-label="Link a repository" @submit.prevent>
      <v-autocomplete
        v-model:search="search"
        :model-value="null"
        :items="choices"
        item-title="name"
        item-value="id"
        item-props="props"
        label="Link a repository"
        prepend-inner-icon="mdi-source-repository"
        :loading="repos.loadingOptions.value"
        :error-messages="repos.optionsError.value || undefined"
        :no-data-text="repos.loadingOptions.value ? 'Loading…' : 'No tracked repositories in this org'"
        density="compact"
        hide-details="auto"
        return-object
        @update:model-value="link"
      />
    </form>
    <ul v-if="repos.linked.value.length" class="repos__list" aria-label="Linked repositories">
      <li v-for="repo in repos.linked.value" :key="repo.id" class="repos__row">
        <v-icon icon="mdi-source-repository" size="18" aria-hidden="true" />
        <a v-if="repo.url" :href="repo.url" target="_blank" rel="noopener noreferrer" class="repos__name">{{ repo.name }}</a>
        <span v-else class="repos__name">{{ repo.name }}</span>
        <v-btn v-if="!disabled" variant="text" size="small" class="repos__unlink" @click="unlinking = repo">Unlink</v-btn>
      </li>
    </ul>
    <AppEmptyState
      v-else
      icon="mdi-source-repository"
      title="No repositories linked"
      body="Link the repositories this board's work lands in, so cards can name one and the board can be filtered by it."
    />
    <AppConfirmDialog
      v-model="unlinkOpen"
      :title="`Unlink ${unlinking?.name ?? ''}?`"
      body="Cards on this board that name it will have their repository cleared. You can link it again later."
      action="Unlink"
      color="error"
      :busy="status.saving.value"
      @confirm="confirmUnlink"
    />
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useRepoSettings } from '@/composables/useRepoSettings'
import type { BoardRepoRead, RepoOption } from '@/types/boards'
import { plural } from '@/utils/format'

const props = defineProps<{ status: BoardSettingsStatus; disabled: boolean }>()

const repos = useRepoSettings(useBoardContext(), props.status)
const search = ref('')
const unlinking = ref<BoardRepoRead | null>(null)
const unlinkOpen = computed({
  get: () => unlinking.value !== null,
  set: open => {
    if (!open) unlinking.value = null
  },
})
// Linked ones stay in the list, greyed, so it's clear they're already here.
const choices = computed(() =>
  repos.options.value.map(o => ({ ...o, props: { disabled: o.linked, subtitle: o.linked ? 'Linked' : undefined } })),
)

async function link(option: RepoOption | null): Promise<void> {
  if (!option || option.linked) return
  search.value = ''
  await repos.link(option)
}

async function confirmUnlink(): Promise<void> {
  if (unlinking.value && (await repos.unlink(unlinking.value))) unlinking.value = null
}

onMounted(() => {
  if (!props.disabled) void repos.loadOptions()
})
</script>

<style scoped>
.repos__add {
  max-width: 420px;
  margin-bottom: 16px;
}
.repos__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.repos__row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  color: rgb(var(--v-theme-on-surface-variant));
}
.repos__row:first-child {
  border-top: 0;
}
.repos__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
  font: 500 14px var(--font-mono);
  color: rgb(var(--v-theme-on-surface));
}
a.repos__name {
  color: var(--color-accent-text);
  text-decoration: none;
}
a.repos__name:hover {
  text-decoration: underline;
}
</style>
