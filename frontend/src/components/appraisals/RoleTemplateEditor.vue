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

<!-- One role template: who it matches, what each heading means for the
     role, which records count, its goal library and whether AI drafts. -->
<template>
  <form class="tpl" @submit.prevent="emit('save', body())">
    <v-text-field v-model="form.name" label="Name" maxlength="80" />
    <div class="tpl__row">
      <v-text-field v-model="departments" label="Departments it matches (comma-separated)" />
      <v-text-field v-model="designations" label="Designations it matches (comma-separated)" />
    </div>
    <h3 class="tpl__heading">What each heading means for this role</h3>
    <v-textarea
      v-for="h in HEADINGS"
      :key="h.value"
      v-model="form.heading_meanings[h.value]"
      :label="h.label"
      rows="1"
      auto-grow
      maxlength="300"
    />
    <h3 class="tpl__heading">Records that count</h3>
    <div class="tpl__sources">
      <v-checkbox
        v-for="source in FACT_SOURCES"
        :key="source"
        v-model="form.fact_sources"
        :value="source"
        :label="sourceLabel(source)"
        density="compact"
        hide-details
      />
    </div>
    <v-switch v-model="form.ai_drafting" color="primary" label="AI drafts check-ins for this role" hide-details />
    <h3 class="tpl__heading">Goal library</h3>
    <div v-for="(goal, i) in form.goal_library" :key="i" class="tpl__goal">
      <v-text-field v-model="goal.title" label="Goal" maxlength="200" density="compact" hide-details />
      <v-text-field v-model="goal.measure" label="How you'll know" maxlength="200" density="compact" hide-details />
      <v-text-field v-model="goal.measure_source" label="Where from" maxlength="200" density="compact" hide-details />
      <v-btn icon="mdi-close" variant="text" size="small" :aria-label="`Remove goal ${i + 1}`" @click="form.goal_library.splice(i, 1)" />
    </div>
    <div class="tpl__actions">
      <v-btn size="small" variant="outlined" prepend-icon="mdi-plus" @click="addGoal">Add a library goal</v-btn>
      <v-spacer />
      <v-btn type="submit" color="primary" :loading="saving">Save template</v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { RoleTemplate, RoleTemplateBody } from '@/types/roleTemplate'
import { FACT_SOURCES, HEADINGS, sourceLabel } from '@/utils/appraisalCheckIn'

const props = defineProps<{ template: RoleTemplate; saving: boolean }>()
const emit = defineEmits<{ save: [body: RoleTemplateBody] }>()

const form = reactive<RoleTemplateBody>({
  name: '',
  match_departments: [],
  match_designations: [],
  heading_meanings: {},
  fact_sources: [],
  goal_library: [],
  ai_drafting: true,
})
const departments = ref('')
const designations = ref('')

watch(
  () => props.template,
  t => {
    Object.assign(form, JSON.parse(JSON.stringify({
      name: t.name,
      match_departments: t.match_departments,
      match_designations: t.match_designations,
      heading_meanings: t.heading_meanings,
      fact_sources: t.fact_sources,
      goal_library: t.goal_library,
      ai_drafting: t.ai_drafting,
    })))
    departments.value = t.match_departments.join(', ')
    designations.value = t.match_designations.join(', ')
  },
  { immediate: true },
)

function addGoal(): void {
  form.goal_library.push({ title: '', measure: '', measure_source: '', trend_id: null })
}

function terms(text: string): string[] {
  return text.split(',').map(t => t.trim()).filter(Boolean)
}

function body(): RoleTemplateBody {
  return {
    ...form,
    match_departments: terms(departments.value),
    match_designations: terms(designations.value),
    goal_library: form.goal_library.filter(g => g.title.trim() && g.measure.trim()),
  }
}
</script>

<style scoped>
.tpl {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tpl__row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.tpl__heading {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 600;
}
.tpl__sources {
  display: flex;
  flex-wrap: wrap;
  gap: 0 16px;
}
.tpl__goal {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 2fr) minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.tpl__actions {
  display: flex;
  gap: 8px;
}
@media (max-width: 700px) {
  .tpl__row,
  .tpl__goal {
    grid-template-columns: 1fr;
  }
}
</style>
