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

<!-- A history as a timeline, in the order given: each event's row comes
     from the renderer registered for its type (utils/activity.ts), with
     the time on the right. -->
<template>
  <div class="activity-timeline">
    <div v-if="loading" class="d-flex justify-center py-6">
      <v-progress-circular indeterminate size="24" />
    </div>
    <div v-else-if="events.length === 0" class="text-center text-medium-emphasis py-6">
      {{ emptyText }}
    </div>
    <v-timeline v-else density="compact" side="end" truncate-line="both">
      <v-timeline-item
        v-for="row in rows"
        :key="row.id"
        :dot-color="row.renderer.color"
        :icon="row.renderer.icon"
        size="x-small"
      >
        <div class="tl-row">
          <div class="tl-content">
            <div class="tl-primary" :class="{ 'text-error': row.view.tone === 'error' }">
              <ActivityParts :parts="row.view.primary" />
            </div>
            <div v-if="row.view.meta?.length" class="tl-meta">
              <ActivityParts :parts="row.view.meta" />
            </div>
            <div v-if="row.view.lines?.length" class="tl-meta">
              <div v-for="(line, i) in row.view.lines" :key="i" class="text-caption">{{ line }}</div>
            </div>
          </div>

          <span class="tl-time" :title="fullTime(row.at)">{{ relativeTime(row.at, new Date(), { style: 'short' }) }}</span>
        </div>
      </v-timeline-item>
    </v-timeline>
  </div>
</template>

<script setup lang="ts" generic="E extends ActivityEvent">
import { computed } from 'vue'
import ActivityParts from '@/components/common/ActivityParts.vue'
import { rendererFor, type ActivityEvent, type ActivityRenderers } from '@/utils/activity'
import { relativeTime } from '@/utils/date'

const props = withDefaults(
  defineProps<{
    events: E[]
    loading: boolean
    renderers: ActivityRenderers<E>
    /** The event's type, the key its renderer is registered under. */
    typeOf: (event: E) => string
    emptyText?: string
  }>(),
  { emptyText: 'No activity yet' },
)

const rows = computed(() =>
  props.events.map(event => {
    const renderer = rendererFor(props.renderers, props.typeOf(event))
    return { id: event.id, at: event.created_at, renderer, view: renderer.row(event) }
  }),
)

function fullTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.activity-timeline {
  padding: 8px 0;
}
/* Row layout: content left, time right */
.tl-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-height: 28px;
}
.tl-content {
  flex: 1;
  min-width: 0;
}
/* Primary line: inline text + chips */
.tl-primary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 13px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.75);
}
/* Meta line: badges below primary */
.tl-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
/* Timestamp: right-aligned, muted */
.tl-time {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.35);
  white-space: nowrap;
  padding-top: 2px;
  cursor: default;
}
</style>
