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

<!-- A form's note that someone else changed what it edits while I was
     typing: load theirs, or save to keep mine. -->
<template>
  <AppCallout v-if="show" variant="warning" role="alert" title="Someone else changed these settings">
    Your edits aren't saved yet. Load the latest to see their change, or save to keep yours.
    <template #actions>
      <v-btn variant="outlined" size="small" @click="emit('reload')">Load the latest</v-btn>
    </template>
  </AppCallout>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'

defineProps<{ show: boolean }>()
const emit = defineEmits<{ reload: [] }>()
</script>
