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

<!-- Import over a Trello connection (full comment history and real files),
     for people who may configure integrations. Not connected: Connect
     opens the key and token form. Connected: who as, Disconnect, and a
     picker of the connected member's boards to read. -->
<template>
  <div class="connect-card">
    <h3 class="connect-card__title">Connect Trello</h3>
    <p class="connect-card__text">Full comment history and real attachment files, read straight from Trello.</p>

    <v-progress-linear v-if="connection.loading.value" indeterminate color="primary" aria-label="Checking the Trello connection" />
    <TrelloCredentialForm
      v-else-if="entering"
      :connection="connection"
      @cancel="entering = false"
      @connected="entering = false"
    />
    <template v-else-if="connected">
      <div class="connect-card__status">
        <AppTag color="success">Connected</AppTag>
        <span v-if="connection.settings.value?.member_username">as @{{ connection.settings.value.member_username }}</span>
        <v-btn variant="text" size="small" :loading="connection.saving.value" @click="connection.disconnect()">Disconnect</v-btn>
      </div>
      <v-select
        v-model="boardId"
        :items="connection.boards.value"
        item-title="name"
        item-value="id"
        label="Board to import"
        :loading="connection.loadingBoards.value"
        :error-messages="connection.boardsError.value || undefined"
        :no-data-text="connection.loadingBoards.value ? 'Loading boards…' : 'No open boards on this Trello account'"
        density="compact"
        :hide-details="!connection.boardsError.value"
      />
      <v-btn color="primary" class="connect-card__go" :loading="busy" :disabled="!boardId || disabled" @click="boardId && emit('read', boardId)">
        Read board and review
      </v-btn>
    </template>
    <template v-else>
      <AppCallout v-if="connection.error.value" variant="error" role="alert">{{ connection.error.value }}</AppCallout>
      <v-btn color="primary" class="connect-card__go" @click="entering = true">Connect</v-btn>
      <p class="connect-card__note">Connected once for everyone in the organisation.</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import TrelloCredentialForm from '@/components/boards/imports/TrelloCredentialForm.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppTag from '@/components/common/AppTag.vue'
import type { TrelloConnection } from '@/composables/useTrelloConnection'

const props = defineProps<{ connection: TrelloConnection; busy: boolean; disabled: boolean }>()
const emit = defineEmits<{ read: [trelloBoardId: string] }>()

const entering = ref(false)
const boardId = ref<string | null>(null)
const connected = computed(() => !!props.connection.settings.value?.configured)

onMounted(() => {
  if (!props.connection.settings.value) void props.connection.load()
})
</script>

<style scoped>
.connect-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 10px;
  border: 1px solid rgb(var(--v-theme-rule));
  background: rgb(var(--v-theme-surface));
}
.connect-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.connect-card__text {
  margin: 0;
  font-size: 13px;
}
.connect-card__status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.connect-card__go {
  align-self: flex-start;
}
.connect-card__note {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
