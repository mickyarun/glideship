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

<!-- What a move to another board changes, before it's sent: the new key
     and what the card loses (labels, people, its repository), and, from a
     members-only board, who gets to read it. What a refusal says sits
     under it, with its way on ("Open card"). -->
<template>
  <div class="move-preview">
    <div v-if="changes.length" class="move-preview__changes">
      <div class="move-preview__head">What changes</div>
      <ul class="move-preview__list">
        <li v-for="line in changes" :key="line">{{ line }}</li>
      </ul>
    </div>
    <AppCallout v-if="membersOnly && targetName" variant="warning" icon="mdi-eye-outline">
      Everyone who can see {{ targetName }} will see this card's comments, checklist and history.
    </AppCallout>
    <AppCallout
      v-if="feedback.toastOpen.value && feedback.toast.value"
      :variant="feedback.toast.value.error ? 'error' : 'warning'"
      role="alert"
    >
      {{ feedback.toast.value.text }}
      <template v-if="feedback.toast.value.action" #actions>
        <v-btn variant="outlined" size="small" @click="feedback.toast.value.action.run()">
          {{ feedback.toast.value.action.label }}
        </v-btn>
      </template>
    </AppCallout>
  </div>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'

defineProps<{
  changes: string[]
  /** The card comes from a members-only board, so moving it widens who reads it. */
  membersOnly: boolean
  targetName: string | null
  feedback: ReturnType<typeof useBoardFeedback>
}>()
</script>

<style scoped>
.move-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.move-preview__head {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.move-preview__list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 20px;
  color: rgb(var(--v-theme-ink-2));
}
</style>
