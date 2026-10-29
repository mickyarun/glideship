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

<!-- Why the board can't be changed: it's archived, or I'm a viewer. A
     viewer is told which admins to ask for edit access. -->
<template>
  <AppCallout v-if="archived" variant="warning" icon="mdi-archive-outline">
    This board is archived. Its cards can be read but not changed until an admin restores it.
  </AppCallout>
  <AppCallout v-else variant="info" icon="mdi-eye-outline">
    You can view this board but not change it.
    <template v-if="admins.length"> Ask {{ admins }} for edit access.</template>
    <template v-else> Ask a board admin for edit access.</template>
  </AppCallout>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import AppCallout from '@/components/common/AppCallout.vue'
import { boardsApi } from '@/services/boardsApi'

const props = defineProps<{ boardKey: string; archived: boolean }>()

const admins = ref('')

// Names only; a viewer may read the member list, and if it fails the
// generic line is enough.
watch(
  () => props.boardKey,
  async key => {
    admins.value = ''
    try {
      const names = (await boardsApi.members(key)).members.filter(m => m.role === 'admin').map(m => m.name)
      const last = names.pop()
      admins.value = names.length ? `${names.join(', ')} or ${last}` : (last ?? '')
    } catch (err) {
      console.error('[boards] members fetch failed:', err)
    }
  },
  { immediate: true },
)
</script>
