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

<!-- "Boards / {board} / {page}" above a board page's title. -->
<template>
  <nav aria-label="Breadcrumb" class="board-crumbs">
    <router-link :to="{ name: 'boards' }">Boards</router-link>
    <span aria-hidden="true">/</span>
    <router-link :to="{ name: 'board', params: { key: board.key } }">{{ board.name }}</router-link>
    <span aria-hidden="true">/</span>
    <span aria-current="page">{{ current }}</span>
  </nav>
</template>

<script setup lang="ts">
import type { BoardRead } from '@/types/boards'

defineProps<{ board: Pick<BoardRead, 'key' | 'name'>; current: string }>()
</script>

<style scoped>
.board-crumbs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
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
</style>
