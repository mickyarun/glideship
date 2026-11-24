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

<!-- Where goals can come from, beside the list: what the person suggested,
     the role library, ideas from their work (AI), and last period's goals. -->
<template>
  <div class="sources">
    <AppPanel v-if="proposed.length" :title="`${who} suggested`">
      <div v-for="goal in proposed" :key="goal.id" class="sources__item">
        <span class="sources__title">{{ goal.title }}</span>
        <span v-if="goal.measure" class="sources__muted">{{ goal.measure }}</span>
        <v-btn size="small" color="primary" variant="flat" :disabled="full && !goal.replaces" @click="emit('accept', goal)">Confirm</v-btn>
      </div>
    </AppPanel>
    <AppPanel v-if="library.length" title="Role library" note="Goals HR set up for this role">
      <div v-for="option in library" :key="option.title" class="sources__item">
        <span class="sources__title">{{ option.title }}</span>
        <span v-if="option.measure" class="sources__muted">{{ option.measure }}</span>
        <v-btn size="small" variant="outlined" @click="emit('pick', option)">Add</v-btn>
      </div>
    </AppPanel>
    <AppPanel title="Ideas from their work" note="AI · check before adding">
      <div v-for="goal in ideas" :key="goal.id" class="sources__item">
        <span class="sources__title">{{ goal.title }}</span>
        <span v-if="goal.why" class="sources__muted">{{ goal.why }}</span>
        <v-btn v-if="goal.actions.accept" size="small" variant="outlined" @click="emit('accept', goal)">Add</v-btn>
      </div>
      <p v-if="!ideas.length" class="sources__muted">{{ canSuggest ? 'Nothing yet.' : 'AI ideas are off for this cycle.' }}</p>
      <v-btn v-if="canSuggest" size="small" variant="text" :loading="pending" @click="emit('suggest')">Get ideas</v-btn>
    </AppPanel>
    <AppPanel v-if="lastPeriod.length" title="From last period">
      <div v-for="option in lastPeriod" :key="option.title" class="sources__item">
        <span class="sources__title">{{ option.title }}</span>
        <v-btn size="small" variant="outlined" @click="emit('pick', option)">Carry over</v-btn>
      </div>
    </AppPanel>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { Goal, GoalOption } from '@/types/appraisalGoals'

const props = defineProps<{ goals: Goal[]; options: GoalOption[]; who: string; full: boolean; canSuggest: boolean; pending: boolean }>()
const emit = defineEmits<{ accept: [goal: Goal]; pick: [option: GoalOption]; suggest: [] }>()
const proposed = computed(() => props.goals.filter(g => g.status === 'proposed'))
const ideas = computed(() => props.goals.filter(g => g.status === 'suggested'))
const library = computed(() => props.options.filter(o => o.source === 'role_library'))
const lastPeriod = computed(() => props.options.filter(o => o.source === 'last_period'))
</script>

<style scoped>
.sources {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sources__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.sources__title {
  font-size: 14px;
  font-weight: 600;
}
.sources__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
