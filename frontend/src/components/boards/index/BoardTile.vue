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

<!-- A board on the index: its name (a link that stretches over the tile),
     key, my role, a lock when it's members-only, and my star, which sits
     above the link so it stays its own button. -->
<template>
  <article class="board-tile">
    <div class="board-tile__top">
      <span class="board-tile__key">{{ board.key }}</span>
      <v-icon
        v-if="board.visibility === 'members'"
        icon="mdi-lock-outline"
        size="15"
        class="board-tile__lock"
        aria-hidden="true"
      />
      <span v-if="board.visibility === 'members'" class="d-sr-only">Members only</span>
      <v-btn
        :icon="board.starred ? 'mdi-star' : 'mdi-star-outline'"
        variant="text"
        size="small"
        density="comfortable"
        :color="board.starred ? 'gold' : undefined"
        class="board-tile__star"
        :aria-label="board.starred ? `Unstar ${board.name}` : `Star ${board.name}`"
        :aria-pressed="board.starred"
        @click="emit('star', board)"
      />
    </div>
    <h2 class="board-tile__name">
      <router-link :to="{ name: 'board', params: { key: board.key } }" class="board-tile__link">
        {{ board.name }}
      </router-link>
    </h2>
    <div class="board-tile__foot">
      <AppTag sr-prefix="Your role:">{{ ROLE_LABELS[board.role] }}</AppTag>
    </div>
  </article>
</template>

<script setup lang="ts">
import AppTag from '@/components/common/AppTag.vue'
import { ROLE_LABELS } from '@/constants/boards'
import type { CustomBoardItem } from '@/types/boards'

defineProps<{ board: CustomBoardItem }>()
const emit = defineEmits<{ star: [board: CustomBoardItem] }>()
</script>

<style scoped>
.board-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 132px;
  padding: 14px 16px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
  transition: border-color var(--dur-short) var(--ease-out);
}
.board-tile:hover,
.board-tile:focus-within {
  border-color: rgba(var(--v-theme-primary), 0.55);
}
.board-tile__top {
  display: flex;
  align-items: center;
  gap: 6px;
}
.board-tile__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-tile__lock {
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-tile__star {
  position: relative;
  z-index: 1;
  margin-left: auto;
}
.board-tile__name {
  margin: 0;
  font-size: 16px;
  line-height: 22px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.board-tile__link {
  color: inherit;
  text-decoration: none;
}
.board-tile__link::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
}
.board-tile__link:focus-visible {
  outline: none;
}
.board-tile__link:focus-visible::after {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.board-tile__foot {
  margin-top: auto;
}
@media (pointer: coarse) {
  .board-tile__star {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
