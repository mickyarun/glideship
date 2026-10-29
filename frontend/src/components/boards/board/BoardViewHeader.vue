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

<!-- A board's title row. The name is the switcher's button (B opens it
     too); then my star, who can see the board and my role, and on the
     right Settings (for admins) and New card (for editors). -->
<template>
  <header class="board-head">
    <div class="board-head__intro">
      <h1 class="board-head__title">
        <button
          type="button"
          class="board-head__switch"
          aria-haspopup="dialog"
          :aria-expanded="switcher.open.value"
          :aria-keyshortcuts="SWITCHER_SHORTCUT_KEY.toUpperCase()"
          @click="switcher.show()"
        >
          <span class="board-head__name">{{ detail.board.name }}</span>
          <v-icon icon="mdi-chevron-down" size="22" aria-hidden="true" />
          <span class="d-sr-only">, switch board</span>
        </button>
      </h1>
      <v-btn
        :icon="detail.starred ? 'mdi-star' : 'mdi-star-outline'"
        variant="text"
        size="small"
        :color="detail.starred ? 'gold' : undefined"
        :aria-label="detail.starred ? 'Unstar this board' : 'Star this board'"
        :aria-pressed="detail.starred"
        @click="emit('star')"
      />
      <p class="board-head__meta">
        <span class="board-head__key">{{ detail.board.key }}</span>
        <span class="board-head__sep" aria-hidden="true">·</span>
        <v-icon :icon="visibility.icon" size="15" aria-hidden="true" />{{ visibility.text }}
        <span class="board-head__sep" aria-hidden="true">·</span>
        You're {{ ROLE_LABELS[detail.role].toLowerCase() }}
      </p>
    </div>
    <div class="board-head__actions">
      <v-btn
        v-if="canSettings"
        variant="outlined"
        prepend-icon="mdi-cog-outline"
        :to="{ name: 'board-settings', params: { key: detail.board.key } }"
      >
        Settings
      </v-btn>
      <v-btn v-if="canCreate" color="primary" prepend-icon="mdi-plus" @click="emit('new-card')">New card</v-btn>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { ROLE_LABELS, SWITCHER_SHORTCUT_KEY } from '@/constants/boards'
import type { BoardDetail } from '@/types/boards'

const props = defineProps<{ detail: BoardDetail; canCreate: boolean; canSettings: boolean }>()
const emit = defineEmits<{ star: []; 'new-card': [] }>()

const switcher = useBoardSwitcher()

const visibility = computed(() =>
  props.detail.board.visibility === 'members'
    ? { icon: 'mdi-lock-outline', text: 'Members only' }
    : { icon: 'mdi-domain', text: 'Everyone in the org' },
)
</script>

<style scoped>
.board-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}
.board-head__intro {
  flex: 1 1 320px;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 4px;
}
.board-head__title {
  margin: 0;
  min-width: 0;
  font-size: 28px;
  line-height: 34px;
  font-weight: 600;
  letter-spacing: var(--tracking-display);
}
.board-head__switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.board-head__meta {
  flex-basis: 100%;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.board-head__key {
  font: 500 12px var(--font-mono);
}
.board-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 600px) {
  .board-head__title {
    font-size: 24px;
    line-height: 30px;
  }
}
</style>
