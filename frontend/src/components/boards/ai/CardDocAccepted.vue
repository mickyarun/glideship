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

<!-- Just after I accept an AI draft: the document's new version, and Undo
     for editors when there was a version before it (putting it back makes a
     newer version, so nothing is lost). It goes once the document moves on. -->
<template>
  <AppCallout variant="success" role="status" class="doc-accepted">
    {{ DOC_LABELS[kind] }} is now version {{ version }}.
    <template v-if="canUndo" #actions>
      <v-btn variant="text" size="small" :loading="undoing" @click="emit('undo')">Undo</v-btn>
    </template>
  </AppCallout>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'
import { DOC_LABELS } from '@/constants/boards'
import type { CardDocKind } from '@/types/boards'

defineProps<{
  kind: CardDocKind
  version: number
  /** An editor, and there was a version before the accept to put back. */
  canUndo: boolean
  undoing: boolean
}>()
const emit = defineEmits<{ undo: [] }>()
</script>
