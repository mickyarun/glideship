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

<!-- Review a parsed Trello board before importing: the new board's name
     and key (for a new board), lists to stages, members to people and the
     options. An export that hit Trello's action limit says what's missing
     and, for people who can, offers a Trello connection instead. -->
<template>
  <div class="map-step">
    <AppCallout
      v-if="discovery.warnings.includes('action_cap')"
      variant="warning"
      title="This export hit Trello's 1,000-action limit"
      role="note"
    >
      Older comments aren't in the file, and attachments come in as links only.
      Connect Trello to import the full history and the files instead.
      <div class="map-step__switch">
        <v-btn v-if="canConnect" variant="text" size="small" class="px-0" @click="emit('switch-to-api')">
          Switch to a Trello connection
        </v-btn>
        <span v-else>An org admin can connect Trello for everyone.</span>
      </div>
    </AppCallout>

    <AppPanel v-if="!existingBoard" title="The new board" note="Its stages come from the lists below">
      <div class="map-step__board">
        <BoardNameKeyFields :fields="form.board" :limits="limits" />
        <BoardVisibilityField v-model="form.visibility.value" />
      </div>
    </AppPanel>

    <div class="map-step__columns">
      <AppPanel class="map-step__lists" title="Lists become stages" note="Categories are guessed from names; check each one" flush>
        <ImportListRow
          v-for="(row, i) in form.rows.value"
          :key="row.list.id"
          :row="row"
          :stages="stages"
          :problem="form.problems.value[i] ?? null"
          :name-max="limits?.stage_name_max ?? null"
        />
      </AppPanel>
      <div class="map-step__side">
        <AppPanel v-if="form.people.value.length" title="Members become people" flush>
          <ImportPersonRow
            v-for="row in form.people.value"
            :key="row.member.id"
            :row="row"
            :people="people"
            @pick="id => form.pick(row, id)"
          />
          <p class="map-step__note">Unmatched people are left unassigned. Their comments keep their Trello name.</p>
        </AppPanel>
        <ImportOptionsPanel
          v-model:archived="form.archived.value"
          :archived-count="form.counts.value.archived"
          :dropped="discovery.dropped"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import BoardNameKeyFields from '@/components/boards/BoardNameKeyFields.vue'
import BoardVisibilityField from '@/components/boards/BoardVisibilityField.vue'
import ImportListRow from '@/components/boards/imports/ImportListRow.vue'
import ImportOptionsPanel from '@/components/boards/imports/ImportOptionsPanel.vue'
import ImportPersonRow from '@/components/boards/imports/ImportPersonRow.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { ImportMappingForm, PickablePerson } from '@/composables/useImportMappingForm'
import type { BoardLimits, StageRead, TrelloDiscovery } from '@/types/boards'

defineProps<{
  form: ImportMappingForm
  discovery: TrelloDiscovery
  /** Importing into a board that exists; its stages can take lists. */
  existingBoard: boolean
  stages: Pick<StageRead, 'id' | 'name' | 'category'>[]
  people: PickablePerson[]
  limits: BoardLimits | null
  /** May use a Trello connection (integrations:configure). */
  canConnect: boolean
}>()
const emit = defineEmits<{ 'switch-to-api': [] }>()
</script>

<style scoped>
.map-step {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.map-step__switch {
  margin-top: 4px;
  font-size: 13px;
}
.map-step__board {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 8px;
}
.map-step__columns {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 18px;
}
.map-step__lists {
  flex: 999 1 560px;
  min-width: 0;
}
.map-step__side {
  flex: 1 1 340px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.map-step__note {
  margin: 0;
  padding: 10px 16px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
