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

<!-- The sections of a board's settings: the settings list beside the page
     on wide screens, a select above it on narrow ones. Either way the open
     section lives in the URL. Admins also get Import from Trello, its own
     page under settings. -->
<template>
  <SettingsSectionNav
    v-if="mdAndUp"
    :groups="groups"
    :current="sectionPath(boardKey, section)"
    label="Board settings sections"
    class="board-settings-nav"
  />
  <v-select
    v-else
    :model-value="section"
    :items="selectItems"
    item-title="title"
    item-value="value"
    label="Section"
    hide-details
    class="board-settings-nav__select"
    @update:model-value="open"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import SettingsSectionNav from '@/components/settings/SettingsSectionNav.vue'
import {
  BOARD_SETTINGS_SECTIONS, importPath, sectionPath, type BoardSettingsSection,
} from '@/utils/boardSettingsSections'

const IMPORT = 'import'

const props = withDefaults(
  defineProps<{ boardKey: string; section: BoardSettingsSection; canImport?: boolean }>(),
  { canImport: false },
)

const router = useRouter()
const { mdAndUp } = useDisplay()

const importItem = computed(() =>
  props.canImport ? [{ title: 'Import from Trello', to: importPath(props.boardKey) }] : [],
)
const groups = computed(() => [
  {
    label: '',
    items: [
      ...BOARD_SETTINGS_SECTIONS.map(s => ({ title: s.title, to: sectionPath(props.boardKey, s.value) })),
      ...importItem.value,
    ],
  },
])
const selectItems = computed(() => [
  ...BOARD_SETTINGS_SECTIONS,
  ...(props.canImport ? [{ value: IMPORT, title: 'Import from Trello' }] : []),
])

function open(section: BoardSettingsSection | typeof IMPORT): void {
  void router.push(section === IMPORT ? importPath(props.boardKey) : sectionPath(props.boardKey, section))
}
</script>

<style scoped>
.board-settings-nav {
  position: sticky;
  top: 24px;
  align-self: start;
}
</style>
