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

<!-- The plan for the next period, once the result is shared: one strength
     to use more, one thing to work on, and next period's goals. Both people
     fill it in, usually in the same 1:1. No rating here. -->
<template>
  <AppPanel :title="`Plan for next ${period}`">
    <p class="growth__muted">You and {{ growth.is_self ? manager : person }} fill this in together, usually in the same 1:1. Either of you can edit it.</p>
    <div class="growth__pair">
      <v-textarea v-model="strength" label="One strength to use more" rows="2" auto-grow maxlength="500" :readonly="!growth.can_edit" />
      <v-textarea v-model="focus" label="One thing to work on" rows="2" auto-grow maxlength="500" :readonly="!growth.can_edit" />
    </div>
    <div v-if="growth.can_edit" class="growth__actions">
      <v-btn variant="outlined" :disabled="!dirty" :loading="busy === 'save'" @click="emit('save', strength.trim(), focus.trim())">Save</v-btn>
    </div>
    <div class="growth__head">
      <h3 class="growth__heading">Goals from {{ longDate(growth.next_period_start) }} · {{ accepted }} of {{ growth.limit }}</h3>
      <v-btn v-if="growth.can_edit" size="small" variant="outlined" prepend-icon="mdi-plus" :disabled="atLimit" @click="emit('add')">Add a goal</v-btn>
    </div>
    <p v-if="!growth.goals.length" class="growth__muted">None yet. A few that matter beat a long list.</p>
    <ul class="growth__goals">
      <li v-for="goal in growth.goals" :key="goal.id" class="growth__goal">
        <div>
          <span class="growth__goal-title">{{ goal.title }}</span>
          <span class="growth__muted"><template v-if="goal.measure">{{ goal.measure }} · </template>{{ standing(goal) }}</span>
        </div>
        <v-btn v-if="goal.can_accept" size="small" color="primary" :disabled="accepted >= growth.limit" @click="emit('accept', goal.id)">Confirm</v-btn>
        <v-btn v-if="goal.can_reject" size="small" variant="outlined" color="error" @click="emit('reject', goal.id)">Reject</v-btn>
        <v-btn v-if="goal.can_remove" size="small" variant="text" @click="emit('remove', goal.id)">{{ growth.is_self ? 'Withdraw' : 'Remove' }}</v-btn>
      </li>
    </ul>
    <AppCallout v-for="goal in growth.rejected" :key="goal.id" variant="warning" :title="`${growth.is_self ? `${upper(manager)} rejected` : 'You rejected'}: ${goal.title}`">
      <template v-if="goal.reason">Reason: {{ goal.reason }}</template>
    </AppCallout>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { GrowthRead, NextGoal } from '@/types/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const props = withDefaults(
  defineProps<{ growth: GrowthRead; busy: string | null; period?: string; manager?: string; person?: string }>(),
  { period: 'quarter', manager: 'your manager', person: 'them' },
)
const emit = defineEmits<{ save: [strength: string, focus: string]; add: []; accept: [goalId: string]; reject: [goalId: string]; remove: [goalId: string] }>()

const strength = ref('')
const focus = ref('')
// Each field follows its own saved value, so saving one doesn't reset an edit to the other.
watch(() => props.growth.strength, s => (strength.value = s), { immediate: true })
watch(() => props.growth.focus, f => (focus.value = f), { immediate: true })
const dirty = computed(() => strength.value.trim() !== props.growth.strength || focus.value.trim() !== props.growth.focus)
const accepted = computed(() => props.growth.goals.filter(g => g.status === 'accepted').length)
// The employee can still propose at the limit; only the manager's adds take a slot.
const atLimit = computed(() => !props.growth.is_self && accepted.value >= props.growth.limit)

function upper(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function standing(goal: NextGoal): string {
  if (goal.status === 'accepted') return 'Confirmed'
  return goal.can_accept ? `Proposed by ${goal.proposed_by_name}` : `Waiting for ${props.growth.is_self ? props.manager : props.person} to confirm`
}
</script>

<style scoped>
.growth__pair {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0 16px;
  margin-top: 12px;
}
.growth__actions {
  display: flex;
  justify-content: flex-end;
}
.growth__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
}
.growth__heading {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.growth__muted {
  display: block;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.growth__goals {
  margin: 0;
  padding: 0;
  list-style: none;
}
.growth__goal {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}
.growth__goal > div {
  flex: 1 1 auto;
}
.growth__goal + .growth__goal {
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.growth__goal-title {
  font-weight: 600;
  font-size: 14px;
}
</style>
