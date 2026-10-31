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

<!-- A card document's versions, newest first, with older pages on demand.
     Picking one asks the Documents tab to compare it with the current text. -->
<template>
  <AppPanel title="Versions">
    <VersionRail
      :items="railItems"
      :selected-id="selectedId"
      :loading="history?.loading ?? true"
      :empty-text="`No versions of the ${DOC_NAMES[kind]} yet.`"
      @select="id => emit('select', id)"
    >
      <template #footer>
        <p v-if="railItems.length > 1" class="doc-versions__hint">Pick a version to see what changed and restore it.</p>
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
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import VersionRail, { type VersionRailItem } from '@/components/common/VersionRail.vue'
import { DOC_NAMES, DOC_SOURCE_BADGES } from '@/constants/boards'
import { useBoardCardDocsStore } from '@/stores/boardCardDocs'
import type { CardDocKind } from '@/types/boards'

const props = defineProps<{ kind: CardDocKind; selectedId: string | null; nameFor: (id: string) => string }>()
const emit = defineEmits<{ select: [id: string] }>()

const docs = useBoardCardDocsStore()
const doc = computed(() => docs.current[props.kind])
const history = computed(() => docs.history[props.kind])

const railItems = computed<VersionRailItem[]>(() =>
  (history.value?.items ?? []).map(v => ({
    id: v.id,
    label: `v${v.version}`,
    at: v.created_at,
    badge: v.version === doc.value?.version ? { text: 'Current', color: 'primary' } : DOC_SOURCE_BADGES[v.source],
    who: v.created_by ? props.nameFor(v.created_by) : null,
  })),
)
</script>

<style scoped>
.doc-versions__hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
