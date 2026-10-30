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

<!-- The sidebar's main links, by workspace: engineering work, team boards,
     engineering insights, then people. Each group shows only to those who
     can open it; the People heading shows when another group sits above. -->
<template>
  <v-list density="compact" nav class="px-2">
    <EngineeringNav v-if="canAccessEngineering" group="work" :rail="rail" />
    <BoardsNav v-if="canViewBoards" :rail="rail" />
    <EngineeringNav v-if="canAccessEngineering" group="insights" :rail="rail" />
    <PeopleNav :rail="rail" :show-heading="canAccessEngineering || canViewBoards" />
  </v-list>
</template>

<script setup lang="ts">
import BoardsNav from '@/components/layout/BoardsNav.vue'
import EngineeringNav from '@/components/layout/EngineeringNav.vue'
import PeopleNav from '@/components/layout/PeopleNav.vue'
import { usePermissions } from '@/composables/usePermissions'

defineProps<{ rail: boolean }>()

const { canAccessEngineering, canViewBoards } = usePermissions()
</script>
