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

<!-- Question 2: what went well. The month's work Glideship found, as a tick
     list; a ticked item can carry a note on why. Free text for anything the
     list missed. Older check-ins' lines show read-only underneath. -->
<template>
  <FormStep :number="2" title="What went well?" :hint="hint">
    <p v-if="!facts.length" class="ci-work__muted">Nothing recorded this month. Say what happened below.</p>
    <ul class="ci-work__list">
      <li v-for="fact in shown" :key="fact.id" class="ci-work__item">
        <label class="ci-work__tick">
          <input type="checkbox" :checked="Boolean(tags[fact.id])" :disabled="!editable" @change="emit('tick', fact.id, !tags[fact.id])" />
          <span><strong>{{ fact.key }}</strong><template v-if="fact.title"> {{ fact.title }}</template></span>
        </label>
        <span class="ci-work__muted">{{ detail(fact) }}</span>
        <v-textarea
          v-if="editable && (tags[fact.id] || opened.has(fact.id))"
          v-model="notes[fact.id]"
          :label="`Your note on ${fact.key}`"
          hint="Optional"
          persistent-hint
          rows="1"
          auto-grow
          maxlength="500"
        />
        <p v-else-if="notes[fact.id]" class="ci-work__note">“{{ notes[fact.id] }}”</p>
        <button v-else-if="editable" type="button" class="ci-work__add" @click="opened.add(fact.id)">+ Add a note on {{ fact.key }}</button>
      </li>
    </ul>
    <v-btn v-if="facts.length > shown.length" size="small" variant="text" @click="all = true">Show {{ facts.length - shown.length }} more</v-btn>
    <v-textarea v-if="editable" v-model="wentWell" label="Anything we missed?" hint="Optional" persistent-hint rows="2" auto-grow maxlength="2000" />
    <p v-else-if="wentWell" class="ci-work__note">“{{ wentWell }}”</p>
    <div v-if="legacy.length" class="ci-work__legacy">
      <span class="ci-work__muted">Written on the earlier form:</span>
      <p v-for="(line, i) in legacy" :key="i" class="ci-work__note">“{{ line }}”</p>
    </div>
  </FormStep>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import FormStep from '@/components/appraisals/FormStep.vue'
import type { CheckInGoal, FactTag, FactView } from '@/types/appraisal'
import { sourceLabel } from '@/utils/appraisalCheckIn'

const FIRST = 5

const props = defineProps<{
  facts: FactView[]
  tags: Record<string, FactTag>
  goals: CheckInGoal[]
  editable: boolean
  manager: string
  month: string
  legacy: string[]
}>()
const emit = defineEmits<{ tick: [factId: string, on: boolean] }>()
const notes = defineModel<Record<string, string>>('notes', { required: true })
const wentWell = defineModel<string>('wentWell', { required: true })
const all = ref(false)
const opened = reactive(new Set<string>())

const hint = computed(() =>
  props.editable
    ? `We found this in Glideship for ${props.month}. Tick what mattered most and add a note on why. Ticked items and your notes go to ${props.manager}.`
    : 'What they ticked from the month\'s work, with their notes.',
)
// Ticked work first, then the rest; others only see what was ticked.
const ordered = computed(() => {
  const ticked = props.facts.filter(f => props.tags[f.id])
  return props.editable ? [...ticked, ...props.facts.filter(f => !props.tags[f.id])] : ticked
})
const shown = computed(() => (all.value ? ordered.value : ordered.value.slice(0, FIRST)))
const titles = computed(() => Object.fromEntries(props.goals.map(g => [g.id, g.title])))

function detail(fact: FactView): string {
  const goal = props.tags[fact.id]?.goal_id
  const done = fact.done_at ? `${fact.verb ?? 'Done'} ${new Date(fact.done_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}` : sourceLabel(fact.source)
  return goal && titles.value[goal] ? `${done} · helps "${titles.value[goal]}"` : done
}
</script>

<style scoped>
.ci-work__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.ci-work__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
}
.ci-work__tick {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
  cursor: pointer;
}
.ci-work__tick input {
  accent-color: rgb(var(--v-theme-primary));
}
.ci-work__muted {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.ci-work__note {
  margin: 0;
  font-size: 14px;
  white-space: pre-line;
}
.ci-work__add {
  align-self: flex-start;
  font-size: 13px;
  color: var(--color-accent-text);
}
.ci-work__legacy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
</style>
