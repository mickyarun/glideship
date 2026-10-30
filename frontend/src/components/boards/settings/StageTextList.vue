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

<!-- A board's stages as text, for anyone who can't change them: in order,
     with each one's category, WIP limit, whether it's the default, its
     handover role and open cards. -->
<template>
  <ol class="stage-text" aria-label="Stages, left to right">
    <li v-for="stage in stages" :key="stage.id" class="stage-text__row">
      <span class="stage-text__name">{{ stage.name }}</span>
      <AppTag :color="CATEGORY_COLORS[stage.category]">{{ CATEGORY_LABELS[stage.category] }}</AppTag>
      <span class="stage-text__meta">{{ stage.wip_limit === null ? 'No WIP limit' : `WIP limit ${stage.wip_limit}` }}</span>
      <AppTag v-if="stage.is_default">Default</AppTag>
      <AppTag v-if="stage.id === board.handover_stage_id" color="category-done">Handover stage</AppTag>
      <AppTag v-if="stage.id === board.return_stage_id" color="category-todo">Return stage</AppTag>
      <span class="stage-text__meta">{{ plural(stage.open_cards, 'open card') }}</span>
    </li>
  </ol>
</template>

<script setup lang="ts">
import AppTag from '@/components/common/AppTag.vue'
import { CATEGORY_COLORS, CATEGORY_LABELS } from '@/constants/boards'
import type { BoardRead, StageRead } from '@/types/boards'
import { plural } from '@/utils/format'

defineProps<{ stages: StageRead[]; board: BoardRead }>()
</script>

<style scoped>
.stage-text {
  margin: 0;
  padding: 0 20px 8px;
  list-style: decimal inside;
}
.stage-text__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 0;
  border-top: 1px solid rgb(var(--v-theme-rule));
  font-size: 14px;
}
.stage-text__name {
  font-weight: 500;
}
.stage-text__meta {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
