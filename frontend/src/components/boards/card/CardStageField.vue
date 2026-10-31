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

<!-- A card's stage in its details: the name and, for anyone who may move
     it, a Change menu of the other stages. A stage the card can't enter
     yet wears a lock and says what it needs. -->
<template>
  <span>{{ stage?.name ?? 'Unknown stage' }}</span>
  <v-menu v-if="canMove && stages.length > 1" location="bottom end">
    <template #activator="{ props: menuProps }">
      <button v-bind="menuProps" type="button" class="stage-field__link" aria-label="Change stage">Change</button>
    </template>
    <v-list density="compact" min-width="200" aria-label="Move to stage">
      <v-list-item
        v-for="s in stages"
        :key="s.id"
        :title="s.id === card.stage_id ? `${s.name} (current)` : s.name"
        :subtitle="s.id === card.stage_id ? undefined : blockReason(card, s)"
        :disabled="s.id === card.stage_id"
        @click="emit('move', s.id)"
      >
        <template v-if="s.id !== card.stage_id && blockReason(card, s)" #append>
          <v-icon icon="mdi-lock-outline" size="16" aria-hidden="true" />
        </template>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CardSummary, StageRead } from '@/types/boards'
import { blockReason } from '@/utils/stageRules'

const props = defineProps<{ card: CardSummary; stages: StageRead[]; canMove: boolean }>()
const emit = defineEmits<{ move: [stageId: string] }>()

const stage = computed(() => props.stages.find(s => s.id === props.card.stage_id) ?? null)
</script>

<style scoped>
.stage-field__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--color-accent-text);
  cursor: pointer;
}
.stage-field__link:hover { text-decoration: underline; }
.stage-field__link:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
@media (pointer: coarse) {
  .stage-field__link { min-height: 44px; }
}
</style>
