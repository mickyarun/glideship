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

<!-- The AI's draft of the month: a few lines under each heading, each with
     the records it came from. Marked as AI so nobody mistakes it for the
     person's own words, and it is never scored. -->
<template>
  <section class="ai" aria-labelledby="checkin-ai">
    <div class="ai__top">
      <h2 id="checkin-ai" class="ai__title">
        <span class="ai__badge">AI draft</span>
        What Glideship made of this month
      </h2>
      <v-btn v-if="canRegenerate" size="small" variant="text" prepend-icon="mdi-refresh" @click="emit('regenerate')">
        Redraft
      </v-btn>
    </div>
    <div v-for="group in groups" :key="group.heading" class="ai__group">
      <h3 class="ai__heading">{{ group.label }}</h3>
      <ul class="ai__lines">
        <li v-for="(line, i) in group.lines" :key="i" class="ai__line">
          {{ line.text }}
          <span class="ai__cites">
            <template v-for="fact in cited(line)" :key="fact.id">
              <a v-if="safeHref(fact.url)" :href="safeHref(fact.url) ?? undefined" class="ai__cite">{{ fact.key }}</a>
              <span v-else class="ai__cite">{{ fact.key }}</span>
              <span class="ai__source">{{ fact.title }}</span>
            </template>
          </span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AiLine, FactView } from '@/types/appraisal'
import { HEADINGS, safeHref } from '@/utils/appraisalCheckIn'

const props = defineProps<{ lines: AiLine[]; facts: FactView[]; canRegenerate: boolean }>()
const emit = defineEmits<{ regenerate: [] }>()

const groups = computed(() =>
  HEADINGS.map(h => ({
    heading: h.value,
    label: h.label,
    lines: props.lines.filter(l => l.section === h.value),
  })).filter(g => g.lines.length),
)

function cited(line: AiLine): FactView[] {
  return props.facts.filter(f => line.fact_ids.includes(f.id))
}
</script>

<style scoped>
.ai {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.ai__top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ai__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.ai__badge {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
}
.ai__group {
  margin-top: 12px;
}
.ai__heading {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
}
.ai__lines {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
}
.ai__line + .ai__line {
  margin-top: 4px;
}
.ai__cites {
  margin-left: 4px;
}
.ai__source {
  margin-left: 4px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
.ai__cite {
  margin-left: 4px;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}
</style>
