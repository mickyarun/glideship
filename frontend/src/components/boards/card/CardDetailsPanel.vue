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
     stage, assignees (anyone who can open the board), labels, priority,
     repository, start and due dates, and when it was made and changed.
     Editors get a Change control on each; viewers read plain text. Each
     field a stage can require is marked (data-card-field) so a refused
     move can bring it into view; while a stage still needs some, a note
     under Stage says which, with Show me. Anyone assigned who lost access
     stays in the picker so they can be taken off. -->
<template>
  <AppPanel title="Details">
    <dl class="bud-facts">
      <dt>Stage</dt>
      <dd class="bud-facts__split">
        <CardStageField :card="card" :stages="stages" :can-move="canMove" @move="emit('move', $event)" />
      </dd>
      <dd v-if="wanted" class="bud-facts__wanted">
        <AppCallout variant="warning" role="status">
          {{ needsWords(wanted.stage.name, wanted.missing) }}
          <template #actions>
            <v-btn variant="text" size="small" color="primary" @click="emit('show-me')">Show me</v-btn>
          </template>
        </AppCallout>
      </dd>

      <dt>Assignees</dt>
      <dd class="bud-facts__split" data-card-field="assignee">
        <span>{{ assigneeNames || 'Unassigned' }}</span>
        <CardPickMenu
          v-if="canEdit"
          :items="memberItems"
          :selected="card.assignee_ids"
          label="assignees"
          empty-text="No one else can open this board"
          @change="emit('assignees', $event)"
        />
      </dd>

      <dt>Labels</dt>
      <dd class="bud-facts__split" data-card-field="label">
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
      <dd class="bud-facts__split" data-card-field="priority">
        <CardPriorityField :priority="card.priority" :editable="canEdit" @change="emit('priority', $event)" />
      </dd>

      <dt>Repository</dt>
      <dd class="bud-facts__split">
        <CardRepoField :repo-id="card.repo_id" :repos="repos" :editable="canEdit" @change="emit('repo', $event)" />
      </dd>

      <dt>Start</dt>
      <dd><CardDateField label="Start" :value="card.start_at" :editable="canEdit" :save="iso => saveDate('start_at', iso)" /></dd>

      <dt>Due</dt>
      <dd data-card-field="due_date">
        <CardDateField label="Due" :value="card.due_at" :editable="canEdit" :save="iso => saveDate('due_at', iso)">
          <v-checkbox
            v-if="card.due_at && canEdit"
            :model-value="card.due_done"
            label="Done"
            aria-label="Mark the due date done"
            density="compact"
            hide-details
            class="bud-facts__done"
            @update:model-value="emit('due-done', !!$event)"
          />
          <span v-else-if="card.due_at && card.due_done" class="bud-facts__muted">Done</span>
        </CardDateField>
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
import CardPriorityField from '@/components/boards/card/CardPriorityField.vue'
import CardRepoField from '@/components/boards/card/CardRepoField.vue'
import CardStageField from '@/components/boards/card/CardStageField.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppTag from '@/components/common/AppTag.vue'
import type { WantedFields } from '@/composables/useCardFieldFocus'
import { labelColor } from '@/constants/boards'
import type { BUDPriority } from '@/types'
import type { BoardPersonRead, BoardRepoRead, CardDetail, LabelRead, StageRead } from '@/types/boards'
import { pickPeople } from '@/utils/boardPeople'
import { formatDate } from '@/utils/date'
import { wordList } from '@/utils/format'
import { needsWords } from '@/utils/stageRules'

const props = defineProps<{
  card: CardDetail
  stages: StageRead[]
  labels: LabelRead[]
  people: BoardPersonRead[]
  /** The people list loaded and is current, so someone missing from it has no access now. */
  peopleKnown: boolean
  repos: BoardRepoRead[]
  nameFor: (id: string) => string
  photoFor: (id: string) => string | null
  /** A stage the card was refused, and what it still needs. */
  wanted?: WantedFields | null
  canEdit: boolean
  canMove: boolean
  saveDate: (field: 'start_at' | 'due_at', iso: string | null) => Promise<boolean>
}>()

const emit = defineEmits<{
  move: [stageId: string]
  assignees: [ids: string[]]
  labels: [ids: string[]]
  priority: [priority: BUDPriority | null]
  repo: [repoId: string | null]
  'due-done': [done: boolean]
  'show-me': []
}>()

const assigneeNames = computed(() => wordList(props.card.assignee_ids.map(props.nameFor)))
const cardLabels = computed(() => props.labels.filter(l => props.card.label_ids.includes(l.id)))
const memberItems = computed<PickItem[]>(() =>
  pickPeople(props.people, props.card.assignee_ids, props.peopleKnown, { nameFor: props.nameFor, photoFor: props.photoFor })
    .map(p => ({ id: p.id, title: p.name, person: true, photo: p.photo, note: p.note })),
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
.bud-facts__wanted {
  grid-column: 1 / -1;
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
.bud-facts__done { flex: 0 0 auto; }
.bud-facts__done :deep(.v-label) { font-size: 14px; }
.bud-facts__done :deep(.v-selection-control) { min-height: 0; }
.bud-facts__muted {
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
