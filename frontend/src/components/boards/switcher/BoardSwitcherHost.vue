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

<!-- The one board switcher, mounted in the app layout: a panel near the
     top of the window on wide screens, a bottom sheet on phones. Opened
     by the board header, the sidebar or the B key outside a text field.
     Both overlays trap focus while open and hand it back on close. -->
<template>
  <v-bottom-sheet v-if="xs" v-model="open" aria-label="Find a board">
    <div class="switcher-host switcher-host--sheet">
      <BoardSwitcher v-if="open" @close="hide" />
    </div>
  </v-bottom-sheet>
  <v-dialog
    v-else
    v-model="open"
    width="520"
    location="top"
    content-class="switcher-host__dialog"
    aria-label="Find a board"
  >
    <div class="switcher-host">
      <BoardSwitcher v-if="open" @close="hide" />
    </div>
  </v-dialog>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useDisplay } from 'vuetify'
import BoardSwitcher from '@/components/boards/switcher/BoardSwitcher.vue'
import { useBoardSwitcher } from '@/composables/useBoardSwitcher'
import { SWITCHER_SHORTCUT_KEY } from '@/constants/boards'
import { isPageShortcut } from '@/utils/shortcuts'

const { xs } = useDisplay()
const { open, show, hide } = useBoardSwitcher()

function onKeydown(event: KeyboardEvent): void {
  if (open.value || !isPageShortcut(event, SWITCHER_SHORTCUT_KEY)) return
  event.preventDefault()
  show()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.switcher-host {
  padding: 12px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-rule));
  border-radius: 12px;
}
.switcher-host--sheet {
  border-radius: 16px 16px 0 0;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}
:global(.switcher-host__dialog) {
  margin-top: 12vh;
}
</style>
