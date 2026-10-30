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

<!-- A card's facts beside its content, in the BUD details panel's layout:
     stage, assignees, labels, priority, start and due dates, and when it
     was made and changed. Editors get a Change control on each; viewers
     read plain text. -->
<template>
  <AppPanel title="Details">
    <dl class="bud-facts">
      <dt>Stage</dt>
      <dd class="bud-facts__split">
        <span>{{ stage?.name ?? 'Unknown stage' }}</span>
        <v-menu v-if="canMove && stages.length > 1" location="bottom end">
          <template #activator="{ props: menuProps }">
            <button v-bind="menuProps" type="button" class="bud-facts__link" aria-label="Change stage">Change</button>
          </template>
          <v-list density="compact" min-width="200" aria-label="Move to stage">
            <v-list-item
              v-for="s in stages"
              :key="s.id"
              :title="s.id === card.stage_id ? `${s.name} (current)` : s.name"
              :disabled="s.id === card.stage_id"
              @click="emit('move', s.id)"
            />
          </v-list>
        </v-menu>
      </dd>

      <dt>Assignees</dt>
      <dd class="bud-facts__split">
        <span>{{ assigneeNames || 'Unassigned' }}</span>
        <CardPickMenu
          v-if="canEdit"
          :items="memberItems"
          :selected="card.assignee_ids"
          label="assignees"
          empty-text="No members on this board"
          @change="emit('assignees', $event)"
        />
      </dd>

      <dt>Labels</dt>
      <dd class="bud-facts__split">
        <span class="bud-facts__tags">
          <AppTag v-for="l in cardLabels" :key="l.id" :color="labelColor(l.color)" sr-prefix="Label">{{ l.name }}</AppTag>
          <span v-if="!cardLabels.length" class="bud-facts__muted">None</span>
        </span>
        <CardPickMenu
          v-if="canEdit"
          :items="labelItems"
          :selected="card.label_ids"
          label="labels"
          empty-text="This board has no labels yet"
          @change="emit('labels', $event)"
        />
      </dd>

      <dt>Priority</dt>
      <dd>
        <BUDPriorityMenu
          :priority="card.priority"
          :editable="canEdit"
          clearable
          @change="emit('priority', $event)"
          @clear="emit('priority', null)"
        />
        <span v-if="!card.priority && !canEdit" class="bud-facts__muted">None</span>
      </dd>

      <dt>Start</dt>
      <dd><CardDateField label="Start" :value="card.start_at" :editable="canEdit" :save="iso => saveDate('start_at', iso)" /></dd>

      <dt>Due</dt>
      <dd>
        <CardDateField label="Due" :value="card.due_at" :editable="canEdit" :save="iso => saveDate('due_at', iso)" />
        <v-checkbox
          v-if="card.due_at && canEdit"
          :model-value="card.due_done"
          label="Done"
          aria-label="Mark the due date done"
          density="compact"
          hide-details
          @update:model-value="emit('due-done', !!$event)"
        />
        <span v-else-if="card.due_at && card.due_done" class="bud-facts__muted">Done</span>
      </dd>

      <dt>Created</dt>
      <dd>{{ formatDate(card.created_at) }}</dd>
      <dt>Updated</dt>
      <dd>{{ formatDate(card.updated_at) }}</dd>
    </dl>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CardDateField from '@/components/boards/card/CardDateField.vue'
import CardPickMenu, { type PickItem } from '@/components/boards/card/CardPickMenu.vue'
import BUDPriorityMenu from '@/components/buds/detail/BUDPriorityMenu.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppTag from '@/components/common/AppTag.vue'
import { labelColor } from '@/constants/boards'
import type { BUDPriority } from '@/types'
import type { CardDetail, LabelRead, MemberRead, StageRead } from '@/types/boards'
import { formatDate } from '@/utils/date'
import { wordList } from '@/utils/format'

const props = defineProps<{
  card: CardDetail
  stages: StageRead[]
  labels: LabelRead[]
  members: MemberRead[]
  nameFor: (id: string) => string
  canEdit: boolean
  canMove: boolean
  saveDate: (field: 'start_at' | 'due_at', iso: string | null) => Promise<boolean>
}>()

const emit = defineEmits<{
  move: [stageId: string]
  assignees: [ids: string[]]
  labels: [ids: string[]]
  priority: [priority: BUDPriority | null]
  'due-done': [done: boolean]
}>()

const stage = computed(() => props.stages.find(s => s.id === props.card.stage_id) ?? null)
const assigneeNames = computed(() => wordList(props.card.assignee_ids.map(props.nameFor)))
const cardLabels = computed(() => props.labels.filter(l => props.card.label_ids.includes(l.id)))
const memberItems = computed<PickItem[]>(() =>
  props.members.map(m => ({ id: m.user_id, title: m.name, person: true, photo: m.avatar_url })),
)
const labelItems = computed<PickItem[]>(() => props.labels.map(l => ({ id: l.id, title: l.name, color: labelColor(l.color) })))
</script>

<style scoped>
.bud-facts {
  margin: 0;
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 12px;
  font-size: 14px;
}
.bud-facts dt {
  color: rgb(var(--v-theme-on-surface-variant));
}
.bud-facts dd {
  margin: 0;
  min-width: 0;
}
.bud-facts__split {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.bud-facts__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.bud-facts__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--color-accent-text);
  cursor: pointer;
}
.bud-facts__link:hover { text-decoration: underline; }
.bud-facts__link:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.bud-facts__muted {
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (pointer: coarse) {
  .bud-facts__link {
    min-height: 44px;
  }
}
</style>
