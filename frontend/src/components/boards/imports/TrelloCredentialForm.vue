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

<!-- Connect Trello for the org: an API key and a read-scoped token. They
     go to the server, which checks them with Trello and stores them
     encrypted; the fields clear once that worked and nothing is ever read
     back into them. -->
<template>
  <form class="trello-creds" @submit.prevent="submit">
    <p class="trello-creds__help">
      Get both from <a :href="TRELLO_ADMIN_URL" target="_blank" rel="noopener noreferrer">Trello's Power-Up admin page</a>.
      Read access is enough. They're stored encrypted.
    </p>
    <v-text-field
      v-model="apiKey"
      label="API key"
      autocomplete="off"
      spellcheck="false"
      class="trello-creds__mono"
      hide-details="auto"
      autofocus
    />
    <v-text-field
      v-model="token"
      label="Token"
      type="password"
      autocomplete="off"
      spellcheck="false"
      class="trello-creds__mono"
      hide-details="auto"
    />
    <AppCallout v-if="connection.error.value" variant="error" role="alert">{{ connection.error.value }}</AppCallout>
    <div class="trello-creds__actions">
      <v-btn variant="text" @click="emit('cancel')">Cancel</v-btn>
      <v-btn type="submit" color="primary" variant="flat" :loading="connection.saving.value" :disabled="!ready">
        Connect
      </v-btn>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import type { TrelloConnection } from '@/composables/useTrelloConnection'

const TRELLO_ADMIN_URL = 'https://trello.com/power-ups/admin'

const props = defineProps<{ connection: TrelloConnection }>()
const emit = defineEmits<{ cancel: []; connected: [] }>()

const apiKey = ref('')
const token = ref('')
const ready = computed(() => !!apiKey.value.trim() && !!token.value.trim() && !props.connection.saving.value)

async function submit(): Promise<void> {
  if (!ready.value) return
  const ok = await props.connection.connect(apiKey.value, token.value)
  if (!ok) return
  apiKey.value = ''
  token.value = ''
  emit('connected')
}
</script>

<style scoped>
.trello-creds {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.trello-creds__help {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.trello-creds__mono :deep(input) {
  font-family: var(--font-mono);
}
.trello-creds__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
