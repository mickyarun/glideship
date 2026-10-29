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

<!-- Find a board: a search box over Starred, Recent, Other boards and
     Delivery, searched on the server. Focus stays in the box; the arrow
     keys move the highlighted row, Enter opens it (Cmd/Ctrl+Enter in a
     new tab) and Esc closes. Typing a card key offers to jump to it. -->
<template>
  <div class="switcher">
    <v-text-field
      ref="input"
      v-model="search.query.value"
      placeholder="Find a board, or type a card key"
      prepend-inner-icon="mdi-magnify"
      density="comfortable"
      hide-details
      autofocus
      role="combobox"
      aria-label="Find a board"
      aria-autocomplete="list"
      :aria-expanded="options.length > 0"
      :aria-controls="listId"
      :aria-activedescendant="activeId"
      :loading="search.loading.value"
      @keydown="onKeydown"
    />
    <p v-if="message" class="switcher__message" role="status">{{ message }}</p>
    <div :id="listId" role="listbox" aria-label="Boards" class="switcher__list">
      <div v-for="group in search.groups.value" :key="group.id" role="group" :aria-labelledby="`${listId}-${group.id}`">
        <div :id="`${listId}-${group.id}`" class="switcher__group">{{ group.label }}</div>
        <div
          v-for="option in group.options"
          :id="`${listId}-${option.id}`"
          :key="option.id"
          role="option"
          class="switcher__option"
          :class="{ 'switcher__option--active': option.id === active?.id }"
          :aria-selected="option.id === active?.id"
          @mousemove="activeIndex = options.indexOf(option)"
          @click="choose(option, $event.metaKey || $event.ctrlKey)"
        >
          <v-icon :icon="ICONS[option.kind]" size="18" aria-hidden="true" />
          <span class="switcher__label">{{ option.label }}</span>
          <span v-if="option.kind === 'board'" class="switcher__key">{{ option.board.key }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useRouter, type RouteLocationRaw } from 'vue-router'
import { useSwitcherSearch } from '@/composables/useSwitcherSearch'
import { boardsApi } from '@/services/boardsApi'
import { extractApiError } from '@/utils/errors'
import { stepIndex, type SwitcherOption } from '@/utils/switcherOptions'

const emit = defineEmits<{ close: [] }>()

const ICONS: Record<SwitcherOption['kind'], string> = {
  card: 'mdi-card-text-outline',
  board: 'mdi-view-column-outline',
  delivery: 'mdi-source-branch',
}

const router = useRouter()
const search = useSwitcherSearch()
const listId = useId()
const activeIndex = ref(0)
const jumpError = ref('')

const options = computed(() => search.options.value)
const active = computed(() => options.value[activeIndex.value] ?? null)
const activeId = computed(() => (active.value ? `${listId}-${active.value.id}` : undefined))
const message = computed(() => {
  if (jumpError.value) return jumpError.value
  if (search.error.value) return search.error.value
  if (!search.loading.value && !options.value.length) return 'No boards match.'
  return ''
})

search.reset()
watch(search.query, () => {
  activeIndex.value = 0
  jumpError.value = ''
})

function open(to: RouteLocationRaw, newTab: boolean): void {
  if (newTab) {
    window.open(router.resolve(to).href, '_blank', 'noopener')
  } else {
    void router.push(to)
    emit('close')
  }
}

async function choose(option: SwitcherOption, newTab = false): Promise<void> {
  if (option.kind === 'board') return open({ name: 'board', params: { key: option.board.key } }, newTab)
  if (option.kind === 'delivery') return open(option.path, newTab)
  try {
    const card = await boardsApi.cardByKey(option.cardKey)
    open({ name: 'board-card', params: { key: card.board_key, number: card.number } }, newTab)
  } catch (err) {
    jumpError.value = extractApiError(err, `No card ${option.cardKey} that you can open.`)
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = stepIndex(activeIndex.value, event.key === 'ArrowDown' ? 1 : -1, options.value.length)
  } else if (event.key === 'Enter' && active.value) {
    event.preventDefault()
    void choose(active.value, event.metaKey || event.ctrlKey)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
  }
}
</script>

<style scoped>
.switcher {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}
.switcher__message {
  margin: 4px 4px 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
.switcher__list {
  overflow-y: auto;
  max-height: min(60vh, 420px);
}
.switcher__group {
  padding: 10px 8px 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: var(--tracking-label);
  text-transform: uppercase;
  color: rgb(var(--v-theme-muted));
}
.switcher__option {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 8px;
  cursor: pointer;
}
.switcher__option--active {
  color: var(--color-accent-text);
  background: var(--color-accent-soft);
}
.switcher__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.switcher__key {
  font: 500 12px var(--font-mono);
  color: rgb(var(--v-theme-on-surface-variant));
}
@media (pointer: coarse) {
  .switcher__option {
    min-height: 44px;
  }
}
</style>
