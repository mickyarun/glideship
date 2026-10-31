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

<!-- One switcher row: key, name, a lock for members-only boards, and a
     short note. Board rows are real links, so a middle click or
     Cmd/Ctrl+click opens a new tab; a plain click is handled here. -->
<template>
  <a
    :id="id"
    :href="href"
    role="option"
    tabindex="-1"
    class="switcher-row"
    :class="{ 'switcher-row--active': active, 'switcher-row--current': option.kind === 'board' && option.current }"
    :aria-selected="active"
    :aria-current="option.kind === 'board' && option.current ? 'page' : undefined"
    @mousemove="emit('hover')"
    @click="onClick"
    @auxclick="onAuxClick"
  >
    <span v-if="option.kind === 'board'" class="switcher-row__key">{{ option.board.key }}</span>
    <span v-else-if="option.kind === 'delivery'" class="switcher-row__key">{{ DELIVERY_BOARD.key }}</span>
    <v-icon v-else icon="mdi-card-text-outline" size="18" aria-hidden="true" />
    <span class="switcher-row__label">{{ option.label }}</span>
    <template v-if="option.kind === 'board' && option.board.visibility === 'members'">
      <v-icon icon="mdi-lock-outline" size="14" aria-hidden="true" />
      <span class="d-sr-only">Members only</span>
    </template>
    <span v-if="option.kind !== 'card'" class="switcher-row__meta">{{ option.meta }}</span>
  </a>
</template>

<script setup lang="ts">
import { DELIVERY_BOARD } from '@/constants/boards'
import type { SwitcherOption } from '@/utils/switcherOptions'

const props = defineProps<{ id: string; option: SwitcherOption; href?: string; active: boolean }>()
const emit = defineEmits<{ hover: []; choose: [newTab: boolean] }>()

function onClick(event: MouseEvent): void {
  const newTab = event.metaKey || event.ctrlKey
  // A link with a modifier opens its own new tab natively.
  if (newTab && props.href) return
  event.preventDefault()
  emit('choose', newTab)
}

// Middle click: native for links; the card row has no link, so open it here.
function onAuxClick(event: MouseEvent): void {
  if (event.button !== 1 || props.href) return
  event.preventDefault()
  emit('choose', true)
}
</script>

<style scoped>
.switcher-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 8px;
  color: inherit;
  text-decoration: none;
  cursor: pointer;
}
.switcher-row--active {
  background: var(--color-accent-soft);
}
.switcher-row__key {
  min-width: 40px;
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
.switcher-row__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.switcher-row--current .switcher-row__label {
  font-weight: 600;
}
.switcher-row__meta {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface-variant));
  white-space: nowrap;
}
@media (pointer: coarse) {
  .switcher-row {
    min-height: 44px;
  }
}
</style>
