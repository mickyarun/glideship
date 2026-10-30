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

<!-- Sidebar links for team boards, for anyone holding boards:view: my
     starred boards (or, with none starred, the ones I opened last), each
     with its key, then every board and the switcher. It never lists every
     board, and reuses the switcher and list replies already loaded. -->
<template>
  <NavHeading label="Boards" :rail="rail" />
  <v-list-item
    v-for="board in shortcuts"
    :key="board.id"
    :prepend-icon="starred.length ? 'mdi-star-outline' : 'mdi-history'"
    :title="board.name"
    :to="{ name: 'board', params: { key: board.key } }"
    rounded="lg"
  >
    <template v-if="!rail" #append>
      <span class="boards-nav__key">{{ board.key }}</span>
    </template>
  </v-list-item>
  <v-list-item
    prepend-icon="mdi-view-grid-outline"
    title="All boards"
    :to="{ name: 'boards' }"
    exact
    rounded="lg"
  >
    <template v-if="store.loaded && !rail" #append>
      <span class="boards-nav__count">{{ count }}<span class="d-sr-only"> boards</span></span>
    </template>
  </v-list-item>
  <v-list-item
    prepend-icon="mdi-magnify"
    title="Find a board"
    rounded="lg"
    role="button"
    aria-haspopup="dialog"
    :aria-keyshortcuts="SWITCHER_SHORTCUT_KEY.toUpperCase()"
    @click="switcher.show()"
  >
    <template v-if="!rail" #append>
      <kbd class="boards-nav__kbd" aria-hidden="true">{{ SWITCHER_SHORTCUT_KEY.toUpperCase() }}</kbd>
    </template>
  </v-list-item>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import NavHeading from '@/components/layout/NavHeading.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import {
  SIDEBAR_RECENT_LIMIT,
  SIDEBAR_STARRED_LIMIT,
  SWITCHER_SHORTCUT_KEY,
} from '@/constants/boards'
import { useBoardsStore } from '@/stores/boards'

defineProps<{ rail: boolean }>()

const store = useBoardsStore()
const switcher = useBoardSwitcher()

const starred = computed(() => store.nav?.starred ?? [])
const shortcuts = computed(() =>
  starred.value.length
    ? starred.value.slice(0, SIDEBAR_STARRED_LIMIT)
    : (store.nav?.recent ?? []).slice(0, SIDEBAR_RECENT_LIMIT),
)
const count = computed(() => store.customBoards.length)

onMounted(() => {
  void store.fetchNav()
})
</script>

<style scoped>
.boards-nav__key,
.boards-nav__count {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface-variant));
}
.boards-nav__key {
  font-family: var(--font-mono);
}
.boards-nav__kbd {
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 5px;
  border: 1px solid rgb(var(--v-theme-rule));
  font: 500 11px/18px var(--font-mono);
  text-align: center;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
