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

<!-- HR's role templates: the list on the left, the chosen one on the right,
     with its trends underneath. -->
<template>
  <AppPage title="Role templates" subtitle="What each heading means for a role, which records count, and its goals.">
    <template #actions>
      <v-btn variant="text" :to="{ name: 'appraisal-cycles' }">Cycles</v-btn>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="create">New template</v-btn>
    </template>
    <AppCallout v-if="store.error || message" :variant="messageKind">{{ message || store.error }}</AppCallout>
    <v-progress-linear v-if="store.loading && !store.templates.length" indeterminate color="primary" />
    <div v-else class="templates">
      <nav class="templates__list" aria-label="Role templates">
        <button
          v-for="t in store.templates"
          :key="t.id"
          type="button"
          class="templates__item"
          :class="{ 'templates__item--on': t.id === selectedId }"
          @click="selectedId = t.id"
        >
          {{ t.name }}<span v-if="t.is_default" class="templates__default"> · fallback</span>
        </button>
      </nav>
      <div v-if="selected" class="templates__editor">
        <RoleTemplateEditor :template="selected" :saving="saving" @save="save" />
        <TrendsEditor :template="selected" :drafting="drafting" @save="saveTrends" @approve="approve" @draft="draftTrends" />
        <v-btn v-if="!selected.is_default" class="templates__delete" variant="text" color="error" @click="remove">Delete template</v-btn>
      </div>
    </div>
  </AppPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPage from '@/components/common/AppPage.vue'
import RoleTemplateEditor from '@/components/appraisals/RoleTemplateEditor.vue'
import TrendsEditor from '@/components/appraisals/TrendsEditor.vue'
import { useJobSocket } from '@/composables/useJobSocket'
import { useRoleTemplatesStore } from '@/stores/roleTemplates'
import type { RoleTemplateBody, Trend } from '@/types/roleTemplate'

const store = useRoleTemplatesStore()
const jobs = useJobSocket()
const selectedId = ref<string | null>(null)
const selected = computed(() => store.templates.find(t => t.id === selectedId.value) ?? null)
const saving = ref(false)
const drafting = ref(false)
const message = ref('')
const messageKind = ref<'error' | 'success'>('error')

function report(problem: string | null, ok: string): void {
  message.value = problem ?? ok
  messageKind.value = problem ? 'error' : 'success'
}

async function save(body: RoleTemplateBody): Promise<void> {
  if (!selected.value) return
  saving.value = true
  report(await store.update(selected.value.id, body), 'Saved.')
  saving.value = false
}

async function create(): Promise<void> {
  const before = new Set(store.templates.map(t => t.id))
  const blank: RoleTemplateBody = {
    name: 'New role',
    match_departments: [],
    match_designations: [],
    heading_meanings: {},
    fact_sources: ['board_cards'],
    goal_library: [],
    ai_drafting: true,
  }
  report(await store.create(blank), 'Created. Fill it in and save.')
  selectedId.value = store.templates.find(t => !before.has(t.id))?.id ?? selectedId.value
}

async function saveTrends(trends: Trend[]): Promise<void> {
  if (selected.value) report(await store.saveTrends(selected.value.id, trends), 'Saved as a draft; approve it to use it.')
}

async function approve(): Promise<void> {
  if (selected.value) report(await store.approveTrends(selected.value.id), 'Approved. New suggestions use this version.')
}

async function draftTrends(): Promise<void> {
  if (!selected.value) return
  drafting.value = true
  const { jobId, error } = await store.draftTrends(selected.value.id)
  if (!jobId) {
    drafting.value = false
    report(error ?? "Couldn't start the draft.", '')
    return
  }
  jobs.startTracking(jobId, {
    onComplete: async () => {
      drafting.value = false
      await store.fetchAll()
      report(null, 'A draft with sources is ready. Edit it, then approve.')
    },
    onError: (err: string) => {
      drafting.value = false
      report(err || "The draft didn't work. Write the trends by hand instead.", '')
    },
  })
}

async function remove(): Promise<void> {
  if (!selected.value) return
  const problem = await store.remove(selected.value.id)
  report(problem, 'Deleted.')
  if (!problem) selectedId.value = store.templates[0]?.id ?? null
}

onMounted(async () => {
  await store.fetchAll()
  selectedId.value = store.templates[0]?.id ?? null
})
</script>

<style scoped>
.templates {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.templates__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.templates__item {
  padding: 8px 12px;
  border-radius: 8px;
  text-align: left;
  font-size: 14px;
  color: inherit;
  background: transparent;
  border: 0;
  cursor: pointer;
}
.templates__item--on {
  background: rgba(var(--v-theme-primary), 0.1);
  font-weight: 600;
}
.templates__default {
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.templates__editor {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.templates__delete {
  align-self: flex-start;
}
@media (max-width: 800px) {
  .templates {
    grid-template-columns: 1fr;
  }
}
</style>
