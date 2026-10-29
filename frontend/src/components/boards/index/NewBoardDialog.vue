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
     see it. On success it opens the new board. -->
<template>
  <v-dialog v-model="open" width="560" scrollable :fullscreen="xs" aria-labelledby="new-board-title">
    <v-card>
      <v-card-title id="new-board-title" class="new-board__title">New board</v-card-title>
      <v-card-text class="new-board__body">
        <AppCallout v-if="form.loadError.value" variant="error">{{ form.loadError.value }}</AppCallout>
        <v-text-field
          v-model="form.name.value"
          label="Name"
          autofocus
          :counter="limits?.board_name_max"
          :maxlength="limits?.board_name_max"
        />
        <v-text-field
          :model-value="form.key.value"
          label="Key"
          class="new-board__key"
          hint="Card keys start with it, like OPS-12. Letters only; it can't be changed later."
          persistent-hint
          @update:model-value="form.setKey"
        />
        <fieldset class="new-board__group">
          <legend class="new-board__legend">Template</legend>
          <v-radio-group v-model="form.template.value" hide-details>
            <v-radio v-for="t in store.templates" :key="t.id" :value="t.id">
              <template #label>
                <span class="new-board__option">
                  <span class="new-board__option-name">{{ t.name }}</span>
                  <span class="new-board__option-note">
                    {{ t.stages.length ? t.stages.map(s => s.name).join(' → ') : t.description }}
                  </span>
                </span>
              </template>
            </v-radio>
          </v-radio-group>
        </fieldset>
        <fieldset class="new-board__group">
          <legend class="new-board__legend">Who can see it</legend>
          <v-radio-group v-model="form.visibility.value" hide-details>
            <v-radio value="org" label="Everyone in the org can view it" />
            <v-radio value="members" label="Only the people and teams I add" />
          </v-radio-group>
        </fieldset>
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
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import AppCallout from '@/components/common/AppCallout.vue'
import { useNewBoardForm } from '@/composables/useNewBoardForm'
import { useBoardsStore } from '@/stores/boards'

const open = defineModel<boolean>({ required: true })

const store = useBoardsStore()
const form = useNewBoardForm()
const router = useRouter()
const { xs } = useDisplay()
const limits = computed(() => store.limits)

watch(open, isOpen => {
  if (isOpen) void form.reset()
})

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
  gap: 12px;
  padding: 12px 24px !important;
}
.new-board__key :deep(input) {
  font-family: var(--font-mono);
  text-transform: uppercase;
}
.new-board__group {
  border: 0;
  margin: 4px 0 0;
  padding: 0;
}
.new-board__legend {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
}
.new-board__option {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}
.new-board__option-name {
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
}
.new-board__option-note {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.new-board__actions {
  justify-content: flex-end;
  padding: 8px 24px 20px;
}
</style>
