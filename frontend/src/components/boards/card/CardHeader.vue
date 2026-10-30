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
     title (editable in place by editors), who's on it and its dates, and
     the overflow menu. -->
<template>
  <header class="bud-header">
    <nav aria-label="Breadcrumb" class="bud-header__crumbs">
      <router-link :to="{ name: 'boards' }">Boards</router-link>
      <span aria-hidden="true">/</span>
      <router-link :to="{ name: 'board', params: { key: board.key } }">{{ board.name }}</router-link>
      <span aria-hidden="true">/</span>
      <span aria-current="page" class="bud-header__mono">{{ card.key }}</span>
    </nav>

    <div class="bud-header__row">
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

        <div class="bud-header__title card-header__title" role="heading" aria-level="1">
          <BugEditableText :value="card.title" label="Title" :editable="canEdit" required :save="saveTitle" />
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

      <div class="bud-header__actions">
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
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CardMoreMenu from '@/components/boards/card/CardMoreMenu.vue'
import BUDPriorityMenu from '@/components/buds/detail/BUDPriorityMenu.vue'
import BugEditableText from '@/components/bugs/BugEditableText.vue'
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
  labels: LabelRead[]
  people: { id: string; name: string; photo: string | null }[]
  now: Date
  canEdit: boolean
  canArchive: boolean
  saveTitle: (title: string) => Promise<boolean>
}>()

const emit = defineEmits<{
  priority: [priority: BUDPriority | null]
  archive: []
  restore: []
  copied: [ok: boolean]
}>()

const date = computed(() => dateChip(props.card, props.now))
</script>

<style scoped src="../../buds/detail/bud-header.css"></style>
<style scoped>
.card-header__title :deep(.bug-text__value) {
  font: inherit;
  letter-spacing: inherit;
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
