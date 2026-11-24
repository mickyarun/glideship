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

<!-- HR sends a review back to the manager with a note they will read. -->
<template>
  <v-dialog :model-value="open" max-width="520" @update:model-value="v => !v && emit('close')">
    <v-card>
      <v-card-title>Send back to {{ managerName || 'the manager' }}</v-card-title>
      <v-card-text><v-textarea v-model="note" label="What to look at again (they read this)" rows="3" auto-grow maxlength="600" /></v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="emit('close')">Cancel</v-btn>
        <v-btn color="primary" :disabled="!note.trim()" :loading="busy" @click="emit('send', note.trim())">Send back</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ open: boolean; managerName: string | null; busy: boolean }>()
const emit = defineEmits<{ close: []; send: [note: string] }>()
const note = ref('')
// A fresh note each time it opens.
watch(() => props.open, open => open && (note.value = ''))
</script>
