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

<!-- The switcher's footer: All boards (with the count once known), the
     archived boards, New board for people who may create one, and the
     keyboard hint. -->
<template>
  <footer class="switcher-foot">
    <router-link :to="{ name: 'boards' }" @click="emit('navigate')">
      All boards<template v-if="count !== null"> ({{ count }})</template>
    </router-link>
    <router-link :to="{ name: 'boards', query: { archived: '1' } }" @click="emit('navigate')">Archived boards</router-link>
    <button v-if="canCreateBoards" type="button" class="switcher-foot__new" @click="emit('new-board')">New board</button>
    <span class="switcher-foot__keys" aria-hidden="true">↑↓ move · Enter open · ⌘Enter new tab · Esc close</span>
  </footer>
</template>

<script setup lang="ts">
import { usePermissions } from '@/composables/usePermissions'

defineProps<{ count: number | null }>()
const emit = defineEmits<{ navigate: []; 'new-board': [] }>()

const { canCreateBoards } = usePermissions()
</script>

<style scoped>
.switcher-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 10px 8px 2px;
  border-top: 1px solid rgb(var(--v-theme-rule));
  font-size: 13px;
}
.switcher-foot a,
.switcher-foot__new {
  color: var(--color-accent-text);
  text-decoration: none;
  font: inherit;
}
.switcher-foot__keys {
  margin-left: auto;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (max-width: 600px) {
  .switcher-foot__keys {
    display: none;
  }
}
@media (pointer: coarse) {
  .switcher-foot a,
  .switcher-foot__new {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
  }
}
</style>
