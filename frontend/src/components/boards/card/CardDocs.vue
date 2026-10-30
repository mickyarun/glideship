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

<!-- A card's Documents tab: pick the PRD, design brief or notes; read or
     edit it; and its versions beside it. Picking an older version shows
     what changed since, with Restore. -->
<template>
  <div class="card-docs">
    <AppPillToggle v-model="kind" :options="kindOptions" class="card-docs__kinds" />
    <AppCallout v-if="docs.error" variant="error">
      {{ docs.error }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="docs.refresh(kind)">Try again</v-btn>
      </template>
    </AppCallout>
    <div class="card-docs__grid">
      <div class="card-docs__main">
        <v-skeleton-loader v-if="docs.loading" type="paragraph@3" />
        <CardDocCompare
          v-else-if="comparing"
          :kind="kind"
          :version="comparing"
          :current-text="doc?.body_md ?? ''"
          :current-version="doc?.version ?? null"
          :can-edit="canEdit"
          @close="compareId = null"
          @result="(error, success) => emit('result', error, success)"
        />
        <CardDocEditor
          v-else
          :key="kind"
          :kind="kind"
          :doc="doc"
          :card-key="cardKey"
          :can-edit="canEdit"
          :max-length="maxLength"
          @result="(error, success) => emit('result', error, success)"
        />
      </div>
      <aside class="card-docs__aside" :aria-label="`${DOC_LABELS[kind]} versions`">
        <AppPanel title="Versions">
          <VersionRail
            :items="railItems"
            :selected-id="compareId"
            :loading="history?.loading ?? true"
            :empty-text="`No versions of the ${DOC_LABELS[kind].toLowerCase()} yet.`"
            @select="select"
          >
            <template #footer>
              <v-btn
                v-if="history?.next"
                variant="text"
                size="small"
                :loading="history.loading"
                @click="docs.loadVersions(kind, { more: true })"
              >
                Show older versions
              </v-btn>
            </template>
          </VersionRail>
        </AppPanel>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CardDocCompare from '@/components/boards/card/CardDocCompare.vue'
import CardDocEditor from '@/components/boards/card/CardDocEditor.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import VersionRail, { type VersionRailItem } from '@/components/common/VersionRail.vue'
import { DOC_KINDS, DOC_LABELS, DOC_SOURCE_LABELS } from '@/constants/boards'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind } from '@/types/boards'

const props = defineProps<{
  cardKey: string
  canEdit: boolean
  maxLength: number | null
  nameFor: (id: string) => string
}>()
const emit = defineEmits<{ result: [error: string | null, success: string] }>()

const docs = useBoardCardDocsStore()
const kind = ref<CardDocKind>(DOC_KINDS[0])
const compareId = ref<string | null>(null)
const kindOptions = DOC_KINDS.map(k => ({ label: DOC_LABELS[k], value: k }))

const doc = computed(() => docs.current[kind.value])
const history = computed(() => docs.history[kind.value])
const comparing = computed(() => history.value?.items.find(v => v.id === compareId.value) ?? null)

const railItems = computed<VersionRailItem[]>(() =>
  (history.value?.items ?? []).map(v => ({
    id: v.id,
    label: `v${v.version}`,
    at: v.created_at,
    badge: v.version === doc.value?.version ? { text: 'Current', color: 'primary' } : DOC_SOURCE_LABELS[v.source],
    note: v.created_by ? props.nameFor(v.created_by) : null,
  })),
)

function select(id: string): void {
  const picked = history.value?.items.find(v => v.id === id)
  // The current version has nothing to compare with; show the document.
  compareId.value = !picked || picked.version === doc.value?.version ? null : id
}

// A new kind, or a new card opened under the tab: load that history.
watch([kind, () => docs.card], ([k]) => {
  compareId.value = null
  if (!docs.history[k]?.loaded) void docs.loadVersions(k)
}, { immediate: true })
</script>

<style scoped>
.card-docs {
  display: flex;
  flex-direction: column;
  gap: 16px;
  container: card-docs / inline-size;
}
.card-docs__kinds {
  align-self: flex-start;
}
.card-docs__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
  align-items: start;
}
.card-docs__main {
  min-width: 0;
}
@container card-docs (max-width: 860px) {
  .card-docs__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
