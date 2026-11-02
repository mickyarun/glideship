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
     keys move the highlighted row (kept in view), Enter opens it once the
     results match what's typed (Cmd/Ctrl+Enter, or a middle click, opens
     a new tab) and Esc closes. Typing a card key offers to jump to it. -->
<template>
  <div class="switcher">
    <v-text-field
      v-model="search.query.value"
      placeholder="Find a board, or type a card key like OPS-58"
      prepend-inner-icon="mdi-magnify"
      density="comfortable"
      hide-details
      autofocus
      role="combobox"
      aria-label="Find a board or card"
      aria-autocomplete="list"
      :aria-expanded="options.length > 0"
      :aria-controls="listId"
      :aria-activedescendant="activeId"
      :loading="search.loading.value"
      @keydown="onKeydown"
    />
    <p v-if="search.noMatch.value" class="switcher__message" role="status">
      No boards match "{{ search.query.value.trim() }}".
      <router-link :to="{ name: 'boards' }" @click="emit('close')">See all boards</router-link>
    </p>
    <p v-else-if="message" class="switcher__message" role="status">{{ message }}</p>
    <div ref="list" :id="listId" role="listbox" aria-label="Boards" class="switcher__list">
      <div v-for="group in search.groups.value" :key="group.id" role="group" :aria-labelledby="`${listId}-${group.id}`">
        <div :id="`${listId}-${group.id}`" class="switcher__group">{{ group.label }}</div>
        <SwitcherRow
          v-for="option in group.options"
          :id="`${listId}-${option.id}`"
          :key="option.id"
          :option="option"
          :href="hrefOf(option)"
          :active="option.id === active?.id"
          @hover="activeIndex = options.indexOf(option)"
          @choose="newTab => choose(option, newTab)"
        />
      </div>
    </div>
    <SwitcherFooter :count="boards.loaded ? boards.customBoards.length : null" @navigate="emit('close')" @new-board="emit('new-board')" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import SwitcherFooter from '@/components/boards/switcher/SwitcherFooter.vue'
import SwitcherRow from '@/components/boards/switcher/SwitcherRow.vue'
import { useSwitcherSearch } from '@/composables/useSwitcherSearch'
import { boardsApi } from '@/services/boardsApi'
import { useBoardsStore } from '@/stores/boards'
import { extractApiError } from '@/utils/errors'
import { stepIndex, type SwitcherOption } from '@/utils/switcherOptions'

const emit = defineEmits<{ close: []; 'new-board': [] }>()

const router = useRouter()
const route = useRoute()
const boards = useBoardsStore()
const currentKey = computed(() => (route.params.key ? String(route.params.key).toUpperCase() : null))
const search = useSwitcherSearch(currentKey)
const listId = useId()
const list = ref<HTMLElement | null>(null)
const activeIndex = ref(0)
const jumpError = ref('')

const options = computed(() => search.options.value)
const active = computed(() => options.value[activeIndex.value] ?? null)
const activeId = computed(() => (active.value ? `${listId}-${active.value.id}` : undefined))
const message = computed(() => jumpError.value || search.error.value)

search.reset()
watch(search.query, () => {
  activeIndex.value = 0
  jumpError.value = ''
})
// Keep the highlight on a real row as results change, and in view.
watch(() => options.value.length, n => {
  if (activeIndex.value >= n) activeIndex.value = Math.max(0, n - 1)
})
watch(activeId, async id => {
  await nextTick()
  if (id) list.value?.querySelector(`[id="${id}"]`)?.scrollIntoView?.({ block: 'nearest' })
})

function routeOf(option: SwitcherOption): RouteLocationRaw | null {
  if (option.kind === 'board') return { name: 'board', params: { key: option.board.key } }
  if (option.kind === 'delivery') return option.path
  return null
}

function hrefOf(option: SwitcherOption): string | undefined {
  const to = routeOf(option)
  return to ? router.resolve(to).href : undefined
}

function open(to: RouteLocationRaw, newTab: boolean): void {
  if (newTab) {
    window.open(router.resolve(to).href, '_blank', 'noopener')
  } else {
    void router.push(to)
    emit('close')
  }
}

async function choose(option: SwitcherOption, newTab = false): Promise<void> {
  const to = routeOf(option)
  if (to) return open(to, newTab)
  if (option.kind !== 'card') return
  try {
    const card = await boardsApi.cardByKey(option.cardKey)
    open({ name: 'board-card', params: { key: card.board_key, number: card.number } }, newTab)
  } catch (err) {
    jumpError.value = extractApiError(err, `No card ${option.cardKey} that you can open.`)
  }
}

async function onKeydown(event: KeyboardEvent): Promise<void> {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = stepIndex(activeIndex.value, event.key === 'ArrowDown' ? 1 : -1, options.value.length)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const newTab = event.metaKey || event.ctrlKey
    await search.settle()
    if (active.value) void choose(active.value, newTab)
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
.switcher__message a {
  color: var(--color-accent-text);
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
</style>
