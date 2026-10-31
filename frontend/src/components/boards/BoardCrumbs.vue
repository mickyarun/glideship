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

<!-- "Boards / {board}" above a board's title, or "Boards / {board} /
     {page}" above one of its pages (a card, its settings). Shared by team
     boards and the Delivery board, which links to its own route. -->
<template>
  <nav aria-label="Breadcrumb" class="board-crumbs">
    <router-link :to="{ name: 'boards' }">Boards</router-link>
    <span aria-hidden="true">/</span>
    <router-link v-if="current" :to="boardRoute">{{ board.name }}</router-link>
    <span v-else aria-current="page">{{ board.name }}</span>
    <template v-if="current">
      <span aria-hidden="true">/</span>
      <span aria-current="page" :class="{ 'board-crumbs__mono': mono }">{{ current }}</span>
    </template>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import type { BoardRead } from '@/types/boards'

const props = defineProps<{
  board: Pick<BoardRead, 'key' | 'name'>
  /** The page under the board; without it the board is the current page. */
  current?: string
  /** Set the current crumb in the mono face (a card key). */
  mono?: boolean
  /** Where the board crumb goes, when it isn't a team board's own route. */
  to?: RouteLocationRaw
}>()

const boardRoute = computed(() => props.to ?? { name: 'board', params: { key: props.board.key } })
</script>

<style scoped>
.board-crumbs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-crumbs a {
  font-weight: 500;
  color: var(--color-accent-text);
  text-decoration: none;
}
.board-crumbs a:hover {
  text-decoration: underline;
}
.board-crumbs__mono {
  font-family: var(--font-mono);
}
</style>
