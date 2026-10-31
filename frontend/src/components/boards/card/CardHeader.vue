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

<!-- A card page's header, in the BUD header's layout and classes: the
     breadcrumb back to its board, its key, priority, stage and labels, the
     title (editable in place by editors) with the actions beside it on
     every width (History, Move to the next stage for those who may move
     it, and the overflow menu), then who's on it and its dates. -->
<template>
  <header class="bud-header">
    <BoardCrumbs :board="board" :current="card.key" mono />

    <div class="bud-header__main">
      <div class="bud-header__tags">
        <span class="bud-header__mono">{{ card.key }}</span>
        <BUDPriorityMenu
          :priority="card.priority"
          :editable="canEdit"
          clearable
          @change="emit('priority', $event)"
          @clear="emit('priority', null)"
        />
        <span v-if="stage" class="bud-header__stage" :style="{ '--stage': `var(--v-theme-${CATEGORY_COLORS[stage.category]})` }">
          <span class="bud-header__stage-dot" />{{ stage.name }}
        </span>
        <AppTag v-for="label in labels" :key="label.id" :color="labelColor(label.color)" sr-prefix="Label">
          {{ label.name }}
        </AppTag>
      </div>

      <div class="card-header__title-row">
        <CardTitle class="card-header__title" :value="card.title" :editable="canEdit" :max-length="titleMax" :save="saveTitle" />
        <div class="card-header__actions bo-header-actions">
          <v-btn v-if="xs" variant="text" icon="mdi-history" aria-label="History" title="See what changed on this card" @click="emit('history')" />
          <v-btn v-else variant="text" prepend-icon="mdi-history" title="See what changed on this card" @click="emit('history')">
            History
          </v-btn>
          <template v-if="next">
            <v-btn v-if="xs" color="primary" icon="mdi-arrow-right" size="small" :aria-label="`Move to ${next.name}`" :title="`Move to ${next.name}`" @click="emit('move', next.id)" />
            <v-btn v-else color="primary" @click="emit('move', next.id)">Move to {{ next.name }}</v-btn>
          </template>
          <CardMoreMenu
            :board-key="board.key"
            :number="card.number"
            :archived="!!card.archived_at"
            :can-archive="canArchive"
            @archive="emit('archive')"
            @restore="emit('restore')"
            @copied="ok => emit('copied', ok)"
          />
        </div>
      </div>

      <div class="bud-header__meta">
        <span class="card-header__people">
          <template v-if="people.length">
            <AppMonogram v-for="p in people" :key="p.id" :name="p.name" :src="p.photo" :size="24" :title="p.name" />
            {{ wordList(people.map(p => p.name)) }}
          </template>
          <template v-else>Unassigned</template>
        </span>
        <span>Created {{ formatDate(card.created_at) }}</span>
        <span>Updated {{ formatDate(card.updated_at) }}</span>
        <span v-if="date" :class="`card-header__date--${date.tone}`">
          <v-icon :icon="date.icon" size="14" aria-hidden="true" /> {{ date.text }}
        </span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDisplay } from 'vuetify'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import CardMoreMenu from '@/components/boards/card/CardMoreMenu.vue'
import CardTitle from '@/components/boards/card/CardTitle.vue'
import BUDPriorityMenu from '@/components/buds/detail/BUDPriorityMenu.vue'
import AppMonogram from '@/components/common/AppMonogram.vue'
import AppTag from '@/components/common/AppTag.vue'
import { CATEGORY_COLORS, labelColor } from '@/constants/boards'
import type { BUDPriority } from '@/types'
import type { BoardRead, CardDetail, LabelRead, StageRead } from '@/types/boards'
import { dateChip } from '@/utils/cardChips'
import { formatDate } from '@/utils/date'
import { wordList } from '@/utils/format'

const props = defineProps<{
  card: CardDetail
  board: BoardRead
  stage: StageRead | null
  /** The board's stages, left to right: Move to goes to the one after this card's. */
  stages: StageRead[]
  labels: LabelRead[]
  people: { id: string; name: string; photo: string | null }[]
  now: Date
  canEdit: boolean
  canMove: boolean
  canArchive: boolean
  titleMax?: number | null
  saveTitle: (title: string) => Promise<boolean>
}>()

const emit = defineEmits<{
  priority: [priority: BUDPriority | null]
  move: [stageId: string]
  history: []
  archive: []
  restore: []
  copied: [ok: boolean]
}>()

const { xs } = useDisplay()
const date = computed(() => dateChip(props.card, props.now))
const next = computed(() => {
  if (!props.canMove || props.card.archived_at) return null
  const at = props.stages.findIndex(s => s.id === props.card.stage_id)
  return at >= 0 ? (props.stages[at + 1] ?? null) : null
})
</script>

<style scoped src="../../buds/detail/bud-header.css"></style>
<style scoped>
/* The actions share the title's row here, so the main column takes the
   header's full width instead of its BUD flex basis. */
.bud-header__main {
  flex: 0 0 auto;
}
.card-header__title-row {
  display: flex;
  align-items: flex-start;
  gap: 8px 16px;
}
.card-header__title {
  flex: 1 1 auto;
  min-width: 0;
}
.card-header__actions {
  flex-shrink: 0;
}
.card-header__people {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgb(var(--v-theme-ink-2));
}
.card-header__date--error {
  color: rgb(var(--v-theme-error));
}
.card-header__date--warning {
  color: rgb(var(--v-theme-warning));
}
.card-header__date--success {
  color: rgb(var(--v-theme-success));
}
</style>
