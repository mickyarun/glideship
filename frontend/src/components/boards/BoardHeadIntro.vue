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

<!-- The left of a board's header, shared by team boards and the Delivery
     board: the breadcrumb, the board's name as the title with its key and
     a chevron (the button that opens the board switcher; B does too), what
     sits beside the title (a star), and a meta line ending in the B hint. -->
<template>
  <div class="board-intro">
    <BoardCrumbs :board="board" :to="to" />
    <div class="board-intro__title-row">
      <button
        type="button"
        class="board-intro__switch"
        aria-haspopup="dialog"
        :aria-expanded="switcher.open.value"
        :aria-keyshortcuts="shortcut"
        @click="switcher.show()"
      >
        <h1 class="board-intro__name">{{ board.name }}</h1>
        <span class="board-intro__key">{{ board.key }}</span>
        <v-icon icon="mdi-chevron-down" size="20" aria-hidden="true" />
        <span class="d-sr-only">Switch board</span>
      </button>
      <slot name="title" />
    </div>
    <p class="board-intro__meta">
      <slot name="meta" />
      <span class="board-intro__hint">
        <span aria-hidden="true">·</span>
        press <kbd>{{ shortcut }}</kbd> to switch boards
      </span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import BoardCrumbs from '@/components/boards/BoardCrumbs.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { SWITCHER_SHORTCUT_KEY } from '@/constants/boards'

defineProps<{ board: { key: string; name: string }; to?: RouteLocationRaw }>()

const switcher = useBoardSwitcher()
const shortcut = SWITCHER_SHORTCUT_KEY.toUpperCase()
</script>

<style scoped>
.board-intro {
  flex: 1 1 320px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.board-intro__title-row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.board-intro__switch {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 2px 6px;
  margin-left: -6px;
  border-radius: 8px;
  color: inherit;
  font: inherit;
}
.board-intro__switch:hover {
  background: rgb(var(--v-theme-surface-bright));
}
.board-intro__switch:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.board-intro__name {
  margin: 0;
  font-size: 28px;
  line-height: 34px;
  font-weight: 600;
  letter-spacing: var(--tracking-display);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.board-intro__key {
  padding: 1px 7px;
  border-radius: 6px;
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-ink-2));
  background: rgb(var(--v-theme-surface-bright));
}
.board-intro__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-intro__meta kbd {
  padding: 0 5px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 4px;
  font: 500 11px var(--font-mono);
}
@media (max-width: 600px) {
  .board-intro__name {
    font-size: 24px;
    line-height: 30px;
  }
  .board-intro__hint {
    display: none;
  }
}
</style>
