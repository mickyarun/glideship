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

<!-- "Your work in Glideship" ("Work in Glideship" to a reader): what was recorded for the person this month,
     grouped by where it came from, each with the goal it helped. Nothing
     here is written by AI. A fact the viewer can't open shows as a private
     record; it still counts. -->
<template>
  <section class="work" aria-labelledby="checkin-work">
    <h2 id="checkin-work" class="work__title">
      {{ editable ? 'Your work' : 'Work' }} in Glideship
      <span class="work__hint">· recorded for {{ monthLabel }}</span>
    </h2>
    <p v-if="!facts.length" class="work__empty">
      Glideship has nothing recorded for this month. Add what you did under the headings below.
    </p>
    <div v-for="group in groups" :key="group.source" class="work__group">
      <h3 class="work__source">{{ group.label }} · {{ group.facts.length }}</h3>
      <div v-for="fact in group.facts" :key="fact.id" class="work__row">
        <a v-if="safeHref(fact.url) && !fact.private" :href="safeHref(fact.url) ?? undefined" class="work__key">{{ fact.key }}</a>
        <span v-else class="work__key work__key--private">{{ fact.key }}</span>
        <span class="work__what">
          <template v-if="fact.private">Can't be opened by you; it still counts.</template>
          <template v-else>{{ fact.title }}</template>
          <span class="work__when"> · {{ fact.verb }}{{ fact.done_at ? ` ${shortDate(fact.done_at)}` : '' }}</span>
        </span>
        <v-select
          v-if="editable"
          :model-value="tagValue(tags[fact.id])"
          :items="options"
          :aria-label="`${fact.key}: which goal it helped`"
          placeholder="Which goal it helped"
          density="compact"
          hide-details
          clearable
          class="work__tag"
          @update:model-value="(v: string | null) => emit('tag', fact.id, tagFromValue(v))"
        />
        <span v-else class="work__tagged">{{ tagLabel(tags[fact.id]) }}</span>
      </div>
    </div>
    <p class="work__note">Canceled and reopened cards aren't listed. The list is saved when the check-in closes.</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CheckInGoal, FactTag, FactView } from '@/types/appraisal'
import { factsBySource, safeHref, tagFromValue, tagOptions, tagValue } from '@/utils/appraisalCheckIn'

const props = defineProps<{
  facts: FactView[]
  tags: Record<string, FactTag>
  goals: CheckInGoal[]
  editable: boolean
  monthLabel: string
}>()
const emit = defineEmits<{ tag: [itemId: string, tag: FactTag | null] }>()

const groups = computed(() => factsBySource(props.facts))
const options = computed(() => tagOptions(props.goals))

function tagLabel(tag: FactTag | undefined): string {
  const value = tagValue(tag)
  return options.value.find(o => o.value === value)?.title ?? 'No goal picked'
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
</script>

<style scoped>
.work {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.work__title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}
.work__hint,
.work__empty,
.work__note,
.work__when,
.work__tagged {
  font-size: 13px;
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.work__empty,
.work__note {
  margin: 8px 0 0;
}
.work__group + .work__group {
  margin-top: 12px;
}
.work__source {
  margin: 8px 0 4px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.work__row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) 220px;
  gap: 12px;
  align-items: center;
  padding: 8px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
  font-size: 14px;
}
.work__key {
  padding: 2px 8px;
  border-radius: 999px;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  white-space: nowrap;
}
.work__key--private {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  font-family: inherit;
}
@media (max-width: 700px) {
  .work__row {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .work__tag,
  .work__tagged {
    grid-column: 1 / -1;
  }
}
</style>
