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

<!-- What the board says back: a polite live region for announcements
     (always in the page, so screen readers hear each one) and the snackbar,
     with its Undo-style action when there is one. A refusal's snackbar
     waits to be dismissed, since its action ("Open card") is the way on.
     It sits at the bottom end, clear of the board's footer hint. -->
<template>
  <p class="d-sr-only" role="status" aria-live="polite">{{ feedback.announcement.value }}</p>
  <v-snackbar
    v-model="feedback.toastOpen.value"
    :timeout="feedback.toast.value?.persist ? -1 : TOAST_MS"
    :color="feedback.toast.value?.error ? 'error' : undefined"
    location="bottom end"
  >
    {{ feedback.toast.value?.text }}
    <template v-if="feedback.toast.value?.action || feedback.toast.value?.persist" #actions>
      <v-btn v-if="feedback.toast.value?.action" variant="text" color="primary" @click="run">
        {{ feedback.toast.value.action.label }}
      </v-btn>
      <v-btn
        v-if="feedback.toast.value?.persist"
        icon="mdi-close"
        variant="text"
        size="small"
        aria-label="Dismiss"
        @click="feedback.toastOpen.value = false"
      />
    </template>
  </v-snackbar>
</template>

<script setup lang="ts">
import { TOAST_MS } from '@/constants/boards'
import type { useBoardFeedback } from '@/composables/useBoardFeedback'

const props = defineProps<{ feedback: ReturnType<typeof useBoardFeedback> }>()

function run(): void {
  props.feedback.toast.value?.action?.run()
  props.feedback.toastOpen.value = false
}
</script>
