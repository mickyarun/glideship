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

<!-- Confirm deleting a stage. A stage with open cards asks where they go,
     defaulting to the nearest stage of the same category. -->
<template>
  <AppConfirmDialog
    v-model="open"
    :title="stage ? `Delete ${stage.name}?` : ''"
    :action="cards ? 'Move cards and delete' : 'Delete stage'"
    :busy="busy"
    @confirm="confirm"
  >
    <template #body>
      <template v-if="cards">{{ plural(cards, 'open card is', 'open cards are') }} in this stage. Choose where they go first.</template>
      <template v-else>It has no open cards. This can't be undone.</template>
    </template>
    <v-select
      v-if="cards"
      v-model="targetId"
      :items="targets"
      :label="`Move its ${plural(cards, 'card')} to`"
      hide-details
    />
    <AppCallout v-if="error" variant="error" role="alert">{{ error }}</AppCallout>
  </AppConfirmDialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { CATEGORY_LABELS } from '@/constants/boards'
import type { StageRead } from '@/types/boards'
import { defaultMoveTarget } from '@/utils/boardStageRules'
import { plural } from '@/utils/format'

const props = defineProps<{ stage: StageRead | null; stages: StageRead[]; busy: boolean; error: string }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ confirm: [moveTo: StageRead | null] }>()

const targetId = ref<string | null>(null)
const cards = computed(() => props.stage?.open_cards ?? 0)
const targets = computed(() =>
  props.stages
    .filter(s => s.id !== props.stage?.id)
    .map(s => ({ value: s.id, title: `${s.name} (${CATEGORY_LABELS[s.category]})` })),
)

watch(open, isOpen => {
  if (isOpen && props.stage) targetId.value = defaultMoveTarget(props.stages, props.stage)?.id ?? null
})

function confirm(): void {
  // Archived cards can sit in a stage with no open ones, so a target always goes along.
  const target = props.stages.find(s => s.id === targetId.value) ?? null
  emit('confirm', target)
}
</script>
