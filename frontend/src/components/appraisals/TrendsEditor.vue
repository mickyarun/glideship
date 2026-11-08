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

<!-- A role's "what's changing" list. HR writes it or asks the AI for a
     draft with sources; it reaches goal suggestions only once approved. -->
<template>
  <section class="trends" aria-labelledby="trends-title">
    <h3 id="trends-title" class="trends__title">
      What's changing in this role · {{ template.trends_status === 'approved' ? `approved, version ${template.trends_version}` : 'draft, not used yet' }}
    </h3>
    <div v-for="(trend, i) in rows" :key="i" class="trends__row">
      <v-text-field v-model="trend.text" label="Change in the field (never about a person)" maxlength="400" density="compact" hide-details />
      <v-text-field v-model="trend.source_url" label="Source (https)" density="compact" hide-details />
      <v-text-field v-model="trend.as_of" label="As of" placeholder="2026-10" maxlength="20" density="compact" hide-details />
      <v-btn icon="mdi-close" variant="text" size="small" :aria-label="`Remove trend ${i + 1}`" @click="rows.splice(i, 1)" />
    </div>
    <div class="trends__actions">
      <v-btn size="small" variant="outlined" prepend-icon="mdi-plus" :disabled="rows.length >= 6" @click="add">Add a trend</v-btn>
      <v-btn size="small" variant="outlined" :loading="drafting" @click="emit('draft')">Draft with AI</v-btn>
      <v-spacer />
      <v-btn size="small" variant="outlined" :disabled="!valid" @click="emit('save', clean())">Save as draft</v-btn>
      <v-btn size="small" color="primary" :disabled="template.trends_status !== 'draft'" @click="emit('approve')">Approve</v-btn>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RoleTemplate, Trend } from '@/types/roleTemplate'

const props = defineProps<{ template: RoleTemplate; drafting: boolean }>()
const emit = defineEmits<{ save: [trends: Trend[]]; approve: []; draft: [] }>()

const rows = ref<Trend[]>([])
watch(
  () => props.template,
  t => {
    // Edit the waiting draft if there is one, else start from the approved list.
    rows.value = (t.trends_status === 'draft' ? t.trends_draft : t.trends).map(x => ({ ...x }))
  },
  { immediate: true },
)
const valid = computed(() => rows.value.every(t => t.text.trim() && t.source_url.trim().startsWith('https://')))

function add(): void {
  rows.value.push({ id: '', text: '', source_url: 'https://', as_of: new Date().toISOString().slice(0, 7) })
}

function clean(): Trend[] {
  return rows.value.map((t, i) => ({ ...t, id: t.id || `t${i + 1}`, text: t.text.trim(), source_url: t.source_url.trim() }))
}
</script>

<style scoped>
.trends {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trends__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.trends__row {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr) 110px auto;
  gap: 8px;
  align-items: center;
}
.trends__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 700px) {
  .trends__row {
    grid-template-columns: 1fr;
  }
}
</style>
