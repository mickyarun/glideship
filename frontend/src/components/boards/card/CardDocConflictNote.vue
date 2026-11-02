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

<!-- A document editor's note that someone saved a newer version while I
     was writing: compare my draft with theirs, or save mine on top. The
     draft stays either way. -->
<template>
  <AppCallout variant="warning" role="alert" :title="`Someone saved a newer version (v${version})`">
    Your draft isn't saved. Compare it with theirs, or save to make yours v{{ version + 1 }}.
    <template #actions>
      <v-btn variant="outlined" size="small" :aria-pressed="comparing" @click="emit('compare')">
        {{ comparing ? 'Hide comparison' : 'Compare' }}
      </v-btn>
      <v-btn variant="flat" color="primary" size="small" :loading="saving" @click="emit('save')">Save mine</v-btn>
    </template>
  </AppCallout>
</template>

<script setup lang="ts">
import AppCallout from '@/components/common/AppCallout.vue'

defineProps<{ version: number; comparing: boolean; saving: boolean }>()
const emit = defineEmits<{ compare: []; save: [] }>()
</script>
