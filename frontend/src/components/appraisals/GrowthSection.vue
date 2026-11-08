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

<!-- The growth conversation, once the result is shared: one strength to use
     more, one thing to work on, and next period's goals. No band here. -->
<template>
  <section class="growth" aria-labelledby="growth-title">
    <h2 id="growth-title" class="growth__title">Growth conversation</h2>
    <v-textarea v-model="strength" label="One strength to use more" rows="2" auto-grow maxlength="500" :readonly="!growth.can_edit" />
    <v-textarea v-model="focus" label="One thing to work on" rows="2" auto-grow maxlength="500" :readonly="!growth.can_edit" />
    <div v-if="growth.can_edit" class="growth__actions">
      <v-btn variant="outlined" :disabled="!dirty" :loading="busy === 'save'" @click="emit('save', strength.trim(), focus.trim())">Save</v-btn>
    </div>
    <h3 class="growth__heading">Goals for the period from {{ longDate(growth.next_period_start) }} ({{ accepted }} of {{ growth.limit }})</h3>
    <p v-if="!growth.goals.length" class="growth__muted">None yet. Two or three is plenty.</p>
    <ul class="growth__goals">
      <li v-for="goal in growth.goals" :key="goal.id" class="growth__goal">
        <div>
          <span class="growth__goal-title">{{ goal.title }}</span>
          <span class="growth__muted"><template v-if="goal.measure">{{ goal.measure }} · </template>{{ goal.status === 'accepted' ? 'Confirmed' : `Proposed by ${goal.proposed_by_name}` }}</span>
        </div>
        <v-btn v-if="goal.can_accept" size="small" color="primary" :disabled="accepted >= growth.limit" @click="emit('accept', goal.id)">Confirm</v-btn>
        <v-btn v-if="goal.can_remove" size="small" variant="text" @click="emit('remove', goal.id)">Take back</v-btn>
      </li>
    </ul>
    <v-btn v-if="growth.can_edit" size="small" variant="outlined" prepend-icon="mdi-plus" :disabled="atLimit" @click="emit('add')">
      Add a goal for next period
    </v-btn>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { GrowthRead } from '@/types/appraisalReview'
import { longDate } from '@/utils/appraisalSetup'

const props = defineProps<{ growth: GrowthRead; busy: string | null }>()
const emit = defineEmits<{ save: [strength: string, focus: string]; add: []; accept: [goalId: string]; remove: [goalId: string] }>()

const strength = ref('')
const focus = ref('')
// Each field follows its own saved value, so saving one doesn't reset an edit to the other.
watch(() => props.growth.strength, s => (strength.value = s), { immediate: true })
watch(() => props.growth.focus, f => (focus.value = f), { immediate: true })
const dirty = computed(() => strength.value.trim() !== props.growth.strength || focus.value.trim() !== props.growth.focus)
const accepted = computed(() => props.growth.goals.filter(g => g.status === 'accepted').length)
// The employee can still propose at the limit; only the manager's adds take a slot.
const atLimit = computed(() => !props.growth.is_self && accepted.value >= props.growth.limit)
</script>

<style scoped>
.growth {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 880px;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.growth__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.growth__heading {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 600;
}
.growth__actions {
  display: flex;
  justify-content: flex-end;
}
.growth__muted {
  display: block;
  margin: 0;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
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
