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

<!-- "From PDT-1" in a handed-over BUD's header: where it came from, a link
     to the card when I can open its board, or plain words when I can't
     (stores/budOrigin.ts). Nothing for a BUD that wasn't handed over. -->
<template>
  <router-link v-if="link" :to="link" class="origin-chip origin-chip--link" :title="title">
    <v-icon icon="mdi-truck-delivery-outline" size="14" aria-hidden="true" />From {{ cardKey }}
  </router-link>
  <span v-else-if="hidden" class="origin-chip">
    <v-icon icon="mdi-truck-delivery-outline" size="14" aria-hidden="true" />From a board you can't see
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useBudOriginStore } from '@/stores/budOrigin'

const props = defineProps<{ budId: string }>()

const store = useBudOriginStore()
const origin = computed(() => (store.budId === props.budId ? store.origin : null))
const card = computed(() => origin.value?.card ?? null)
const hidden = computed(() => !!origin.value?.hidden)
const cardKey = computed(() => card.value?.key ?? '')
const title = computed(() => (card.value ? `${card.value.key} · ${card.value.title}, on the ${card.value.board.name} board` : ''))
const link = computed(() =>
  card.value ? { name: 'board-card', params: { key: card.value.board.key, number: card.value.number } } : null,
)
</script>

<style scoped>
.origin-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.origin-chip--link {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}
.origin-chip--link:hover {
  text-decoration: underline;
}
</style>
