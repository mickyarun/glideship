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

<!-- The one Appraisals page: the tab strip, then whichever appraisal page
     the route opens. Every appraisal route is a child of this one, so deep
     links keep their paths and names. -->
<template>
  <div class="appraisals">
    <AppraisalTabs class="appraisals__tabs" :has-reports="leaveStore.approvalCount.has_reports" :can-manage="canManageAppraisals" :own-page="ownReview" :counts="todo.counts" />
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppraisalTabs from '@/components/appraisals/AppraisalTabs.vue'
import { usePermissions } from '@/composables/usePermissions'
import { useAppraisalReviewStore } from '@/stores/appraisalReview'
import { useAppraisalTodoStore } from '@/stores/appraisalTodo'
import { useAuthStore } from '@/stores/auth'
import { useLeaveStore } from '@/stores/leave'

const { canManageAppraisals } = usePermissions()
const leaveStore = useLeaveStore()
const route = useRoute()
const reviews = useAppraisalReviewStore()
const auth = useAuthStore()
const todo = useAppraisalTodoStore()
// A review opened by id belongs under "Your own" when it is the viewer's.
// Only once the review on screen is the one in the route, not the last one still loaded.
const ownReview = computed(() => {
  const current = reviews.current
  return route.name === 'appraisal-review' && current?.id === route.params.id && current.user_id === auth.user?.id
})

onMounted(() => {
  void leaveStore.fetchApprovalCount()
})
</script>

<style scoped>
.appraisals {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: rgb(var(--v-theme-background));
}
.appraisals__tabs {
  margin: 16px 36px 0;
}
@media (max-width: 600px) {
  .appraisals__tabs {
    margin: 12px 16px 0;
  }
}
</style>
