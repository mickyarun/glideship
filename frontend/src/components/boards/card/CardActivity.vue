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

<!-- A card's history, newest first, on the shared timeline with the
     card's own rows, and older entries a page at a time. It loads each
     time the tab opens. -->
<template>
  <AppPanel title="Activity">
    <AppCallout v-if="activity.error.value" variant="error" role="alert" title="Activity didn't load" class="mb-3">
      {{ activity.error.value }}
      <template #actions>
        <v-btn variant="outlined" size="small" @click="activity.load()">Try again</v-btn>
      </template>
    </AppCallout>
    <ActivityTimeline
      :events="activity.events.value"
      :loading="activity.loading.value"
      :renderers="renderers"
      :type-of="typeOf"
    />
    <v-btn
      v-if="activity.next.value"
      variant="text"
      size="small"
      :loading="activity.loadingMore.value"
      @click="activity.more()"
    >
      Show older activity
    </v-btn>
  </AppPanel>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import ActivityTimeline from '@/components/common/ActivityTimeline.vue'
import AppCallout from '@/components/common/AppCallout.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import type { useCardActivity } from '@/composables/useCardActivity'
import type { CardEventRead, StageRead } from '@/types/boards'
import { cardTimelineRenderers } from '@/utils/cardTimelineRows'

const props = defineProps<{
  activity: ReturnType<typeof useCardActivity>
  stages: StageRead[]
  nameFor: (id: string) => string
}>()

const renderers = computed(() =>
  cardTimelineRenderers({
    stage: id => props.stages.find(s => s.id === id)?.name ?? 'another stage',
    person: props.nameFor,
  }),
)
const typeOf = (event: CardEventRead) => event.type

// Fresh each time the tab opens.
onMounted(() => void props.activity.load())
</script>
