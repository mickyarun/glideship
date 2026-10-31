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
    <v-card color="surface" class="pa-6">
      <h2 id="new-board-title" class="new-board__title mb-2">New board</h2>
      <v-card-text class="new-board__body">
        <AppCallout v-if="form.loadError.value" variant="error">{{ form.loadError.value }}</AppCallout>
        <BoardNameKeyFields :fields="form" :limits="limits" autofocus />
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
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import BoardNameKeyFields from '@/components/boards/BoardNameKeyFields.vue'
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
/* The same header as the New BUD dialog. */
.new-board__title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
}
.new-board__body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  /* Room above the first field for its floating label, which the
     scrolling body would otherwise clip. */
  padding: 8px 0 0 !important;
}
.new-board__actions {
  justify-content: flex-end;
  padding: 20px 0 0;
}
</style>
