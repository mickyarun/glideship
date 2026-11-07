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

<!-- One block of a guide text file, rendered as text (never HTML). -->
<template>
  <h3 v-if="block.kind === 'heading'" class="guide-block__heading">{{ block.text }}</h3>
  <ul v-else-if="block.kind === 'list'" class="guide-block__list">
    <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
  </ul>
  <p v-else class="guide-block__text">{{ block.text }}</p>
</template>

<script setup lang="ts">
import type { GuideBlock } from '@/utils/guideText'

defineProps<{ block: GuideBlock }>()
</script>

<style scoped>
.guide-block__heading {
  margin: 16px 0 4px;
  font-size: 15px;
  font-weight: 600;
}
.guide-block__text {
  margin: 0 0 8px;
}
.guide-block__list {
  margin: 0 0 8px;
  padding-left: 20px;
}
</style>
