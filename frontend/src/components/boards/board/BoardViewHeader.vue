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
     my role; on the right Metrics (everyone), Settings (admins) and New
     card (editors), which shrink to icon buttons on phones. -->
<template>
  <header class="board-head">
    <BoardHeadIntro :board="detail.board">
      <template #title>
        <v-btn
          :icon="detail.starred ? 'mdi-star' : 'mdi-star-outline'"
          variant="text"
          size="small"
          :color="detail.starred ? 'warning' : undefined"
          :aria-label="detail.starred ? `Unstar ${detail.board.name}` : `Star ${detail.board.name}`"
          :aria-pressed="detail.starred"
          @click="emit('star')"
        />
      </template>
      <template #meta>
        <v-icon :icon="visibility.icon" size="15" aria-hidden="true" />{{ visibility.text }}
        <span aria-hidden="true">·</span>
        {{ rolePhrase(detail.role) }}
      </template>
    </BoardHeadIntro>
    <div class="board-head__actions bo-header-actions">
      <v-btn
        v-if="xs"
        variant="outlined"
        icon="mdi-chart-bar"
        size="small"
        aria-label="Metrics"
        :to="{ name: 'board-metrics', params: { key: detail.board.key } }"
      />
      <v-btn
        v-else
        variant="outlined"
        prepend-icon="mdi-chart-bar"
        :to="{ name: 'board-metrics', params: { key: detail.board.key } }"
      >
        Metrics
      </v-btn>
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
import BoardHeadIntro from '@/components/boards/BoardHeadIntro.vue'
import { rolePhrase, VISIBILITY_LABELS } from '@/constants/boards'
import type { BoardDetail } from '@/types/boards'

const props = defineProps<{ detail: BoardDetail; canCreate: boolean; canSettings: boolean }>()
const emit = defineEmits<{ star: []; 'new-card': [] }>()

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
.board-head__actions {
  flex-wrap: wrap;
}
</style>
