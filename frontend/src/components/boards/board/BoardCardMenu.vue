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

<!-- A card's ⋯ menu: move it to another stage (the keyboard path for
     anything drag does; it lands at the bottom) or to another board, copy
     its link, hand it over to Delivery (on its page, where the dialog
     opens), and archive or restore it. Items the board's capabilities don't allow are
     left out, so a viewer sees only Copy link. A stage the card can't enter
     yet wears a lock and says what it needs; picking it explains and
     offers Open card. -->
<template>
  <v-menu location="bottom end">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        icon="mdi-dots-horizontal"
        variant="text"
        size="x-small"
        density="comfortable"
        class="card-menu__btn"
        :aria-label="`Actions for ${card.key}`"
      />
    </template>
    <!-- A menu: the stages are a group of radio items, the current one
         checked; the rest are menu items. -->
    <v-list density="compact" min-width="220" role="menu" :aria-label="`Actions for ${card.key}`">
      <template v-if="canMove && !card.archived_at && stages.length > 1">
        <div role="group" aria-label="Move to stage">
          <v-list-subheader aria-hidden="true">Move to stage</v-list-subheader>
          <v-list-item
            v-for="stage in stages"
            :key="stage.id"
            role="menuitemradio"
            :aria-checked="stage.id === card.stage_id"
            :aria-disabled="stage.id === card.stage_id"
            :title="stage.id === card.stage_id ? `${stage.name} (current)` : stage.name"
            :subtitle="stage.id === card.stage_id ? undefined : blockReason(card, stage)"
            :disabled="stage.id === card.stage_id"
            @click="emit('move', stage.id)"
          >
            <!-- The stage's category dot, in the icon column, so every item's
                 text starts at the same edge as Copy link and Archive. -->
            <template #prepend>
              <v-icon icon="mdi-circle-medium" :color="CATEGORY_COLORS[stage.category]" aria-hidden="true" />
            </template>
            <template v-if="stage.id !== card.stage_id && blockReason(card, stage)" #append>
              <v-icon icon="mdi-lock-outline" size="16" aria-hidden="true" />
            </template>
          </v-list-item>
        </div>
        <v-divider class="my-1" />
      </template>
      <v-list-item
        v-if="canMove && !card.archived_at"
        role="menuitem"
        prepend-icon="mdi-arrow-right-bold-box-outline"
        title="Move to another board…"
        @click="emit('move-board')"
      />
      <v-list-item
        v-if="canHandOver" role="menuitem" prepend-icon="mdi-truck-delivery-outline"
        :title="card.handovers.some(isLive) ? 'Hand over another…' : 'Hand over to Delivery…'" @click="handOver"
      />
      <v-list-item role="menuitem" prepend-icon="mdi-link-variant" title="Copy link" @click="copy" />
      <template v-if="canArchive">
        <v-list-item
          v-if="card.archived_at"
          role="menuitem"
          prepend-icon="mdi-archive-arrow-up-outline"
          title="Restore"
          @click="emit('restore')"
        />
        <v-list-item v-else role="menuitem" prepend-icon="mdi-archive-outline" title="Archive" @click="emit('archive')" />
      </template>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { CATEGORY_COLORS, HANDOVER_QUERY_KEY } from '@/constants/boards'
import type { CardSummary, StageRead } from '@/types/boards'
import { copyText } from '@/utils/clipboard'
import { isLive } from '@/utils/handoverChips'
import { blockReason } from '@/utils/stageRules'

const props = defineProps<{
  card: CardSummary
  stages: StageRead[]
  boardKey: string
  canMove: boolean
  canArchive: boolean
  /** Hand it over to Delivery: its page opens with the handover dialog. */
  canHandOver?: boolean
}>()

const emit = defineEmits<{ move: [stageId: string]; 'move-board': []; archive: []; restore: []; copied: [] }>()

const router = useRouter()

function handOver(): void {
  void router.push({
    name: 'board-card',
    params: { key: props.boardKey, number: props.card.number },
    query: { [HANDOVER_QUERY_KEY]: '1' },
  })
}

async function copy(): Promise<void> {
  const { href } = router.resolve({
    name: 'board-card',
    params: { key: props.boardKey, number: props.card.number },
  })
  if (await copyText(new URL(href, window.location.origin).toString())) emit('copied')
}
</script>

<style scoped>
@media (pointer: coarse) {
  .card-menu__btn {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
