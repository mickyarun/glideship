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

<!-- A finished import: the counts, what was skipped and who wasn't
     matched, the board to open, and a short checklist for finishing the
     move (the checks are only for the person reading; nothing is saved). -->
<template>
  <div class="done-step">
    <div class="done-step__main">
      <p class="done-step__headline">{{ boardName }} is ready: {{ plural(session.result?.imported ?? 0, 'card') }} imported</p>
      <dl class="done-step__stats">
        <div v-for="stat in stats" :key="stat.label" class="done-step__stat">
          <dt>{{ stat.label }}</dt>
          <dd>{{ stat.value.toLocaleString() }}</dd>
        </div>
      </dl>
      <p v-if="skipped || unmatched" class="done-step__note">{{ [skipped, unmatched].filter(Boolean).join(' ') }}</p>
      <v-btn v-if="session.board_key" color="primary" class="done-step__open" :to="{ name: 'board', params: { key: session.board_key } }">
        Open the {{ boardName }} board
      </v-btn>
    </div>
    <AppPanel class="done-step__cutover" title="Finish moving over">
      <v-checkbox v-for="item in CUTOVER" :key="item" :label="item" density="compact" hide-details />
      <p class="done-step__note">
        Cards added in Trello before you close it can be picked up by importing again. Cards already here aren't duplicated.
      </p>
    </AppPanel>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { ImportSessionRead } from '@/types/boards'
import { plural } from '@/utils/format'
import { importStats, skippedLine, unmatchedLine } from '@/utils/importSummary'

const props = defineProps<{ session: ImportSessionRead; boardName: string }>()

const CUTOVER = [
  'Spot-check a few cards and comments',
  'Tell the team the board has moved',
  'Close the Trello board so nobody keeps using it',
]

const stats = computed(() => importStats(props.session))
const skipped = computed(() => skippedLine(props.session))
const unmatched = computed(() => unmatchedLine(props.session))
</script>

<style scoped>
.done-step {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: flex-start;
}
.done-step__main {
  flex: 1 1 360px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.done-step__headline {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.done-step__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}
.done-step__stat {
  display: flex;
  flex-direction: column-reverse;
  gap: 2px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
.done-step__stat dd {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.done-step__stat dt {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.done-step__note {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.done-step__open {
  align-self: flex-start;
}
.done-step__cutover {
  flex: 1 1 320px;
  min-width: 0;
}
@media (max-width: 600px) {
  .done-step__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
