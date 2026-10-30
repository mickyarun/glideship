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

<!-- A BUD's history: the shared timeline with the BUD's row renderers
     (utils/budTimelineRows.ts). -->
<template>
  <ActivityTimeline :events="events" :loading="loading" :renderers="BUD_TIMELINE_RENDERERS" :type-of="typeOf" />
</template>

<script setup lang="ts">
import ActivityTimeline from '@/components/common/ActivityTimeline.vue'
import type { TimelineEvent } from '@/types'
import { BUD_TIMELINE_RENDERERS } from '@/utils/budTimelineRows'

defineProps<{
  events: TimelineEvent[]
  loading: boolean
}>()

const typeOf = (event: TimelineEvent) => event.event_type
</script>
