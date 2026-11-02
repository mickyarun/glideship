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

<!-- A card document that isn't written yet. When an editor can run a
     by-hand agent that writes this kind, it offers that agent beside
     writing it by hand; otherwise it says how to write one. -->
<template>
  <div v-if="agent" class="doc-empty">
    <p class="doc-empty__title">No {{ DOC_NAMES[kind] }} yet</p>
    <p class="doc-empty__text">Draft one from the card's description and comments, or write it yourself.</p>
    <div class="doc-empty__actions">
      <v-btn
        variant="flat" color="primary" size="small" :prepend-icon="AI_ICON"
        :loading="agents.starting === agent.id" :disabled="!!agents.active || agents.waiting || !!agents.starting"
        @click="agents.run(agent)"
      >
        Run {{ agent.skill_name }}
      </v-btn>
      <v-btn v-if="canEdit" variant="outlined" size="small" @click="emit('write')">Start writing</v-btn>
    </div>
  </div>
  <p v-else class="doc-empty__text">No {{ DOC_NAMES[kind] }} yet.{{ canEdit ? ' Use Edit to write one.' : '' }}</p>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AI_ICON } from '@/constants/boardAgents'
import { DOC_NAMES } from '@/constants/boards'
import { useBoardCardAgentsStore } from '@/stores/boardCardAgents'
import type { CardDocKind } from '@/types/boards'

const props = defineProps<{ kind: CardDocKind; canEdit: boolean; canRun: boolean }>()
const emit = defineEmits<{ write: [] }>()

const agents = useBoardCardAgentsStore()
/** A by-hand agent on the card's stage that writes this document, when I may run it. */
const agent = computed(() => {
  const data = agents.data
  if (!props.canRun || !data?.ai_enabled) return null
  return data.agents.find(a => a.trigger === 'manual' && a.output_kind === props.kind) ?? null
})
</script>

<style scoped>
.doc-empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.doc-empty__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.doc-empty__text {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.doc-empty__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}
</style>
