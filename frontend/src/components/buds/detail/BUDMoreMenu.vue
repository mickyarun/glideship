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

<!-- The header's overflow menu: move to any stage, restore a discarded
     BUD, send a BUD from a card back to it, open the AI skills settings,
     delete. It opens clear of its own button (useMenuRoom), and a click
     that lands while it's opening isn't taken as a pick, so a quick double
     click on the button can't change the stage. -->
<template>
  <v-menu
    ref="menu" v-model="open" :location="room.location.value" :offset="room.offset" :max-height="room.maxHeight.value"
  >
    <template #activator="{ props: menuProps }">
      <v-btn v-bind="menuProps" variant="outlined" icon="mdi-dots-horizontal" aria-label="More actions" />
    </template>
    <!-- A menu (the button says it opens one). The stages are a group of
         radio items, the current one checked; the rest are menu items. -->
    <v-list density="compact" min-width="200" role="menu" aria-label="More actions">
      <div role="group" aria-label="Change stage">
        <v-list-subheader aria-hidden="true">Change stage</v-list-subheader>
        <!-- Discarded is recoverable, closed is not: a closed BUD has already
             run its close-out (XP, SP, learning recap), and reopening it
             would let those fire again. -->
        <v-list-item
          v-if="status === 'discarded' && canEditBuds"
          role="menuitem"
          prepend-icon="mdi-restore"
          @click="pick(() => emit('restore'))"
        >
          <v-list-item-title>Restore BUD</v-list-item-title>
        </v-list-item>
        <v-list-item v-else-if="isClosed" role="menuitem" aria-disabled="true" disabled>
          <v-list-item-title class="text-medium-emphasis">
            {{ status === 'discarded' ? 'Discarded' : 'Closed' }}, so the stage can't change
          </v-list-item-title>
        </v-list-item>
        <template v-else>
          <v-list-item
            v-for="s in statusItems"
            :key="s.value"
            role="menuitemradio"
            :aria-checked="status === s.value"
            :aria-disabled="agentLocked || changingStatus || !canMoveTo(s.value) || status === s.value"
            :title="s.title"
            :active="status === s.value"
            :disabled="agentLocked || changingStatus || !canMoveTo(s.value) || status === s.value"
            @click="pick(() => emit('update-status', s.value))"
          />
        </template>
      </div>
      <v-divider class="my-1" />
      <v-list-item v-if="sendBackTo" role="menuitem" prepend-icon="mdi-keyboard-return" @click="pick(() => emit('send-back'))">
        <v-list-item-title>Send back to {{ sendBackTo }}…</v-list-item-title>
      </v-list-item>
      <v-list-item
        role="menuitem"
        prepend-icon="mdi-tune-variant"
        :aria-disabled="isClosed"
        :disabled="isClosed"
        @click="pick(() => emit('open-skill-settings'))"
      >
        <v-list-item-title>AI skills</v-list-item-title>
      </v-list-item>
      <template v-if="canDelete">
        <v-divider class="my-1" />
        <v-list-item
          role="menuitem"
          base-color="error"
          prepend-icon="mdi-delete-outline"
          :aria-disabled="agentLocked"
          :disabled="agentLocked"
          @click="pick(() => emit('delete'))"
        >
          <v-list-item-title>Delete BUD</v-list-item-title>
        </v-list-item>
      </template>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useMenuRoom } from '@/composables/useMenuRoom'
import type { BUDStatus } from '@/types'

defineProps<{
  status: BUDStatus
  statusItems: ReadonlyArray<{ title: string; value: BUDStatus }>
  isClosed: boolean
  agentLocked: boolean
  changingStatus: boolean
  canEditBuds: boolean
  canMoveTo: (status: BUDStatus) => boolean
  canDelete: boolean
  /** The board a BUD from a card can be sent back to; null when it can't. */
  sendBackTo?: string | null
}>()

const emit = defineEmits<{
  'update-status': [status: BUDStatus]
  restore: []
  'send-back': []
  'open-skill-settings': []
  delete: []
}>()

const open = ref(false)
const menu = ref<{ activatorEl?: Element | null } | null>(null)
const room = useMenuRoom()
watch(open, isOpen => {
  if (isOpen) room.opened(menu.value?.activatorEl)
}, { flush: 'sync' })

/** Run an item's action unless the click was the end of the one that opened the menu. */
function pick(run: () => void): void {
  if (!room.picking()) return
  open.value = false
  void nextTick(run)
}
</script>
