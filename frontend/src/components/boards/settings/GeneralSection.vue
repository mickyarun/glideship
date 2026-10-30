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

<!-- General: the board's name and description. The key starts every
     card's key and is fixed once the board exists. Saved with the page's
     Save button. -->
<template>
  <AppPanel title="General">
    <DraftConflictNote :show="form.conflict.value" class="mb-4" @reload="form.reset()" />
    <div v-if="form.draft.value" class="general">
      <v-text-field
        v-model="form.draft.value.name"
        label="Name"
        :maxlength="limits?.board_name_max"
        :error-messages="form.nameError.value || undefined"
        :disabled="disabled"
        hide-details="auto"
      />
      <v-text-field
        :model-value="board.key"
        label="Key"
        readonly
        :disabled="disabled"
        class="general__key"
        :hint="`Cards are ${board.key}-1, ${board.key}-2… The key can't be changed.`"
        persistent-hint
      />
      <v-textarea
        v-model="form.draft.value.description"
        label="Description"
        rows="3"
        auto-grow
        :counter="limits?.board_description_max"
        :error-messages="form.descriptionError.value || undefined"
        :disabled="disabled"
        hide-details="auto"
        class="general__description"
      />
    </div>
  </AppPanel>
</template>

<script setup lang="ts">
import DraftConflictNote from '@/components/boards/settings/DraftConflictNote.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { useGeneralForm } from '@/composables/useBoardSettingsForms'
import type { BoardLimits, BoardRead } from '@/types/boards'

defineProps<{
  form: ReturnType<typeof useGeneralForm>
  board: BoardRead
  limits: BoardLimits | null
  disabled: boolean
}>()
</script>

<style scoped>
.general {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 16px;
}
.general__description {
  grid-column: 1 / -1;
}
.general__key :deep(input) {
  font-family: var(--font-mono);
}
@media (max-width: 600px) {
  .general {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
