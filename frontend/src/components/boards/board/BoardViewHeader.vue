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

<!-- A board's title area: the breadcrumb, then the name and key as the
     switcher's button (B opens it too), my star, who can see the board and
     my role; on the right Settings (admins) and New card (editors), which
     shrinks to a + button on phones. -->
<template>
  <header class="board-head">
    <div class="board-head__intro">
      <nav aria-label="Breadcrumb" class="board-head__crumbs">
        <router-link :to="{ name: 'boards' }">Boards</router-link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">{{ detail.board.name }}</span>
      </nav>
      <div class="board-head__title-row">
        <button
          type="button"
          class="board-head__switch"
          aria-haspopup="dialog"
          :aria-expanded="switcher.open.value"
          :aria-keyshortcuts="SWITCHER_SHORTCUT_KEY.toUpperCase()"
          @click="switcher.show()"
        >
          <h1 class="board-head__name">{{ detail.board.name }}</h1>
          <span class="board-head__key">{{ detail.board.key }}</span>
          <v-icon icon="mdi-chevron-down" size="20" aria-hidden="true" />
          <span class="d-sr-only">Switch board</span>
        </button>
        <v-btn
          :icon="detail.starred ? 'mdi-star' : 'mdi-star-outline'"
          variant="text"
          size="small"
          :color="detail.starred ? 'warning' : undefined"
          :aria-label="detail.starred ? `Unstar ${detail.board.name}` : `Star ${detail.board.name}`"
          :aria-pressed="detail.starred"
          @click="emit('star')"
        />
      </div>
      <p class="board-head__meta">
        <v-icon :icon="visibility.icon" size="15" aria-hidden="true" />{{ visibility.text }}
        <span aria-hidden="true">·</span>
        {{ rolePhrase(detail.role) }}
        <span class="board-head__hint">
          <span aria-hidden="true">·</span>
          press <kbd>{{ SWITCHER_SHORTCUT_KEY.toUpperCase() }}</kbd> to switch boards
        </span>
      </p>
    </div>
    <div class="board-head__actions">
      <v-btn
        v-if="canSettings"
        variant="outlined"
        :prepend-icon="xs ? undefined : 'mdi-cog-outline'"
        :to="{ name: 'board-settings', params: { key: detail.board.key } }"
      >
        Settings
      </v-btn>
      <template v-if="canCreate">
        <v-btn v-if="xs" color="primary" icon="mdi-plus" size="small" aria-label="New card" @click="emit('new-card')" />
        <v-btn v-else color="primary" prepend-icon="mdi-plus" @click="emit('new-card')">New card</v-btn>
      </template>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDisplay } from 'vuetify'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { rolePhrase, SWITCHER_SHORTCUT_KEY, VISIBILITY_LABELS } from '@/constants/boards'
import type { BoardDetail } from '@/types/boards'

const props = defineProps<{ detail: BoardDetail; canCreate: boolean; canSettings: boolean }>()
const emit = defineEmits<{ star: []; 'new-card': [] }>()

const switcher = useBoardSwitcher()
const { xs } = useDisplay()

const visibility = computed(() => VISIBILITY_LABELS[props.detail.board.visibility])
</script>

<style scoped>
.board-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
}
.board-head__intro {
  flex: 1 1 320px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.board-head__crumbs {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-head__crumbs a {
  color: var(--color-accent-text);
  text-decoration: none;
}
.board-head__crumbs a:hover {
  text-decoration: underline;
}
.board-head__title-row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.board-head__switch {
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
.board-head__switch:hover {
  background: rgb(var(--v-theme-surface-bright));
}
.board-head__switch:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.board-head__name {
  margin: 0;
  font-size: 28px;
  line-height: 34px;
  font-weight: 600;
  letter-spacing: var(--tracking-display);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.board-head__key {
  padding: 1px 7px;
  border-radius: 6px;
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-ink-2));
  background: rgb(var(--v-theme-surface-bright));
}
.board-head__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-head__meta kbd {
  padding: 0 5px;
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 4px;
  font: 500 11px var(--font-mono);
}
.board-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 600px) {
  .board-head__name {
    font-size: 24px;
    line-height: 30px;
  }
  .board-head__hint {
    display: none;
  }
}
</style>
