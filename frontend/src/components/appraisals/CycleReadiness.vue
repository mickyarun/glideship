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

<!-- Before a cycle opens: AI or manual and why, who won't be enrolled, who
     gets the general template, and accounts that may need merging. -->
<template>
  <section class="ready" aria-labelledby="ready-title">
    <h2 id="ready-title" class="ready__title">Readiness · {{ readiness.in_scope }} people in scope</h2>
    <AppCallout :variant="readiness.drafting === 'ai' ? 'success' : 'info'" :title="readiness.drafting === 'ai' ? 'AI drafts are ready' : 'Manual check-ins'">
      {{ readiness.ai_note || 'Check-ins get AI lines on top of the work list. Everyone can still change or ignore them.' }}
    </AppCallout>
    <ReadinessList
      v-if="readiness.no_primary_manager.length"
      title="Not enrolled: no primary manager"
      hint="Set a primary manager on their employee record; they're picked up until the enrolment cut-off."
      :people="readiness.no_primary_manager.map(p => p.name)"
    />
    <ReadinessList
      v-if="readiness.no_template.length"
      title="Using the general role template"
      hint="No template matches their department or designation."
      :people="readiness.no_template.map(p => p.name)"
    />
    <ReadinessList
      v-if="readiness.identity.length"
      title="Work may sit on another account"
      hint="Merge these accounts first so their work shows in their check-ins."
      :people="readiness.identity.map(f => `${f.name}: maybe ${f.maybe.map(m => m.name).join(', ')}`)"
    />
    <p v-if="allClear" class="ready__clear">Everyone in scope has a primary manager and a role template.</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import ReadinessList from '@/components/appraisals/ReadinessList.vue'
import type { Readiness } from '@/types/appraisalSetup'

const props = defineProps<{ readiness: Readiness }>()
const allClear = computed(
  () => !props.readiness.no_primary_manager.length && !props.readiness.no_template.length && !props.readiness.identity.length,
)
</script>

<style scoped>
.ready {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.ready__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.ready__clear {
  margin: 0;
  font-size: 14px;
}
</style>
