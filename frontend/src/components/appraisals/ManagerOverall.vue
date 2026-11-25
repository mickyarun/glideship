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

<!-- The overall rating in the manager's review: the person's rating and
     reason, then Agree or Change. Changing opens the same five-word scale
     and examples when the new rating needs them. The manager's words to
     the person are always written; they are the reason for a change too. -->
<template>
  <div class="mgr-overall">
    <div>
      <span class="mgr-overall__said">{{ theirs ? bandLabel(theirs) : 'No self-review' }}</span>
      <p v-if="theirs && review.self_score?.reason" class="mgr-overall__muted">“{{ review.self_score.reason }}”</p>
    </div>
    <AppPillToggle
      :model-value="form.agree ? 'agree' : 'change'"
      :options="agreeOrChange(theirs !== null)"
      aria-label="Agree or change the overall rating"
      @update:model-value="choose"
    />
    <template v-if="!form.agree">
      <BandScale v-model="form.band" label="Your overall rating" show-legend />
      <EvidencePicker v-model="form.evidence" :options="options" label="Examples" />
      <p class="mgr-overall__muted">{{ needLine }}</p>
    </template>
    <v-textarea
      v-model="form.reason"
      :label="`Your words for ${who}`"
      :hint="form.agree ? `${who} reads this in the result.` : `${who} reads this in the result. Say why you changed the rating.`"
      persistent-hint
      rows="3"
      auto-grow
      maxlength="600"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppPillToggle from '@/components/common/AppPillToggle.vue'
import BandScale from '@/components/appraisals/BandScale.vue'
import EvidencePicker from '@/components/appraisals/EvidencePicker.vue'
import type { AppraisalRead, EvidenceOption, ManagerBody } from '@/types/appraisalReview'
import { bandLabel, evidenceNeeded } from '@/utils/appraisalBands'
import { agreeOrChange } from '@/utils/appraisalReview'

const props = defineProps<{ review: AppraisalRead; options: EvidenceOption[]; who: string }>()
const form = defineModel<ManagerBody>({ required: true })
// Only a sent self-review counts; a draft is nobody else's to agree with.
const theirs = computed(() => (props.review.self_score?.submitted_at ? props.review.self_score.band : null))
// Examples only back a change, so agreeing drops any picked before.
function choose(value: string): void {
  form.value.agree = value === 'agree'
  if (form.value.agree) form.value.evidence = []
}

const needLine = computed(() => {
  const needed = evidenceNeeded(form.value.band, true)
  if (!needed) return 'Examples are optional for this rating.'
  return `"${bandLabel(form.value.band)}" needs ${needed === 1 ? 'an example' : `${needed} examples`}. You have ${form.value.evidence.length}.`
})
</script>

<style scoped>
.mgr-overall {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}
.mgr-overall > :deep(.v-input),
.mgr-overall > .band-scale {
  width: 100%;
}
.mgr-overall__said {
  font-size: 14px;
  font-weight: 600;
}
.mgr-overall__muted {
  margin: 2px 0 0;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface-variant));
}
</style>
