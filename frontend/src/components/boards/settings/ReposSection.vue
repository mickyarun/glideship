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
     a card can name one, the board can be filtered by it and AI on the
     board reads only these. Admins link one from the org's active
     repositories (already linked ones show but can't be picked again; an
     org with none is pointed to its repository settings) and unlink,
     which asks first and says how many open cards lose it when that's
     known. Everyone else reads the list. -->
<template>
  <AppPanel title="Repositories" :note="INTRO">
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
        :no-data-text="noData"
        density="compact"
        hide-details="auto"
        return-object
        @update:model-value="link"
      />
    </form>
    <AppCallout v-if="orgHasNone" variant="info" class="repos__none">
      This org tracks no repositories yet. Add them in the org's repository settings, then link them here.
      <template #actions>
        <v-btn variant="outlined" size="small" :to="{ name: 'settings-code' }">Repository settings</v-btn>
      </template>
    </AppCallout>
    <ul v-if="repos.linked.value.length" class="repos__list" :aria-label="plural(repos.linked.value.length, 'linked repository', 'linked repositories')">
      <li v-for="repo in repos.linked.value" :key="repo.id" class="repos__row">
        <v-icon icon="mdi-source-repository" size="18" aria-hidden="true" />
        <RepoLink :name="repo.name" :url="repo.url" class="repos__name" />
        <v-btn v-if="!disabled" variant="text" :aria-label="`Unlink ${repo.name}`" @click="unlinking = repo">Unlink</v-btn>
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
      :body="unlinkBody"
      action="Unlink"
      color="error"
      :busy="status.saving.value"
      @confirm="confirmUnlink"
    />
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import RepoLink from '@/components/boards/RepoLink.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppEmptyState from '@/components/common/AppEmptyState.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useBoardContext } from '@/composables/useBoardContext'
import type { BoardSettingsStatus } from '@/composables/useBoardSettingsStatus'
import { useRepoSettings } from '@/composables/useRepoSettings'
import type { BoardRepoRead, RepoOption } from '@/types/boards'
import { plural } from '@/utils/format'

const props = defineProps<{ status: BoardSettingsStatus; disabled: boolean }>()

const INTRO = 'Cards can name one of these; AI on this board reads only these repositories.'

const page = useBoardContext()
const repos = useRepoSettings(page, props.status)
const search = ref('')
const unlinking = ref<BoardRepoRead | null>(null)
const unlinkOpen = computed({
  get: () => unlinking.value !== null,
  set: open => {
    if (!open) unlinking.value = null
  },
})
const loaded = computed(() => !repos.loadingOptions.value && !repos.optionsError.value)
const orgHasNone = computed(() => !props.disabled && loaded.value && repos.optionsLoaded.value && !repos.options.value.length)
const allLinked = computed(() => repos.options.value.length > 0 && repos.options.value.every(o => o.linked))
// Linked ones stay in the list, greyed, so it's clear they're already here.
const choices = computed(() =>
  allLinked.value
    ? []
    : repos.options.value.map(o => ({ ...o, props: { disabled: o.linked, subtitle: o.linked ? 'Linked' : undefined } })),
)
const noData = computed(() => {
  if (repos.loadingOptions.value) return 'Loading…'
  return allLinked.value ? "All of the org's repositories are linked" : 'No tracked repositories in this org'
})
// How many open cards lose it, when the board's loaded cards are all of them.
const unlinkBody = computed(() => {
  const count = unlinking.value ? repos.cardsNaming(unlinking.value.id) : null
  const what = count === null
    ? 'Cards on this board that name it will have their repository cleared.'
    : count === 0
      ? 'No open card on this board names it.'
      : count === 1
        ? '1 open card on this board names it and will have its repository cleared.'
        : `${count} open cards on this board name it and will have their repository cleared.`
  return `${what} You can link it again later.`
})

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
  margin-bottom: 16px;
}
.repos__none {
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
  min-height: 52px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  color: rgb(var(--v-theme-on-surface-variant));
}
.repos__row:first-child {
  border-top: 0;
}
.repos__name {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
}
</style>
