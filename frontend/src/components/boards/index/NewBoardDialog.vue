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

<!-- Create a board: its name, a key that starts every card's key (which
     can't change later), the template its stages come from, and who can
     see it, with what each choice means. On success it opens the board. -->
<template>
  <v-dialog v-model="open" width="640" scrollable :fullscreen="xs" aria-labelledby="new-board-title">
    <v-card>
      <v-card-title id="new-board-title" class="new-board__title">New board</v-card-title>
      <v-card-text class="new-board__body">
        <AppCallout v-if="form.loadError.value" variant="error">{{ form.loadError.value }}</AppCallout>
        <div>
          <div class="new-board__row">
            <v-text-field
              v-model="form.name.value"
              label="Name"
              autofocus
              :maxlength="limits?.board_name_max"
              hide-details="auto"
            />
            <v-text-field
              :model-value="form.key.value"
              label="Key"
              class="new-board__key"
              :maxlength="limits?.board_key_max"
              :aria-describedby="keyHintId"
              hide-details
              @update:model-value="form.setKey"
            />
          </div>
          <p :id="keyHintId" class="new-board__hint">{{ form.keyHint.value }}</p>
        </div>
        <TemplatePicker v-model="form.template.value" :templates="store.templates" />
        <BoardVisibilityField v-model="form.visibility.value" />
        <AppCallout v-if="form.error.value" variant="error">{{ form.error.value }}</AppCallout>
      </v-card-text>
      <v-card-actions class="new-board__actions">
        <v-btn variant="text" @click="open = false">Cancel</v-btn>
        <v-btn color="primary" variant="flat" :loading="form.saving.value" :disabled="!form.canSubmit.value" @click="create">
          Create board
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, useId, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import BoardVisibilityField from '@/components/boards/BoardVisibilityField.vue'
import TemplatePicker from '@/components/boards/index/TemplatePicker.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { useNewBoardForm } from '@/composables/useNewBoardForm'
import { useBoardsStore } from '@/stores/boards'

const open = defineModel<boolean>({ required: true })

const store = useBoardsStore()
const form = useNewBoardForm()
const router = useRouter()
const { xs } = useDisplay()
const limits = computed(() => store.limits)
const keyHintId = useId()

watch(open, isOpen => {
  if (isOpen) void form.reset()
}, { immediate: true })

async function create(): Promise<void> {
  const detail = await form.submit()
  if (!detail) return
  open.value = false
  void router.push({ name: 'board', params: { key: detail.board.key } })
}
</script>

<style scoped>
.new-board__title {
  padding: 20px 24px 4px;
  font-weight: 600;
}
.new-board__body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 12px 24px !important;
}
/* Top-aligned so the name field keeps its own height next to the key. */
.new-board__row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  align-items: start;
  gap: 12px;
}
.new-board__hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.new-board__key :deep(input) {
  font-family: var(--font-mono);
  text-transform: uppercase;
}
@media (max-width: 600px) {
  .new-board__row {
    grid-template-columns: 1fr;
  }
}
.new-board__actions {
  justify-content: flex-end;
  padding: 8px 24px 20px;
}
</style>
