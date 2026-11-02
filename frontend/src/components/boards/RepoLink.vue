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

<!-- A repository's name: a link to its page (in a new tab, marked with an
     open-in-new icon) when its address is https, plain text otherwise, so
     a stored address never runs as script. -->
<template>
  <a v-if="href" :href="href" target="_blank" rel="noopener noreferrer" class="repo-link repo-link--live">
    {{ name }}<v-icon icon="mdi-open-in-new" size="14" class="repo-link__icon" aria-hidden="true" />
    <span class="d-sr-only"> (opens in a new tab)</span>
  </a>
  <span v-else class="repo-link">{{ name }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { safeHref } from '@/utils/safeHref'

const props = defineProps<{ name: string; url: string | null }>()
const href = computed(() => safeHref(props.url))
</script>

<style scoped>
.repo-link {
  font-family: var(--font-mono);
  color: inherit;
  overflow-wrap: anywhere;
}
.repo-link--live {
  color: var(--color-accent-text);
  text-decoration: none;
}
.repo-link--live:hover {
  text-decoration: underline;
}
.repo-link--live:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
.repo-link__icon {
  margin-left: 4px;
  vertical-align: -1px;
}
</style>
