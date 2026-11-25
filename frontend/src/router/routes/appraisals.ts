// Copyright 2025-2026 Arun Rajkumar
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * The one Appraisals page: a tab strip over every appraisal screen. The API
 * decides what each person may see on each; HR-only screens are refused to
 * everyone else by the API too.
 */
import type { RouteRecordRaw } from 'vue-router'

export const appraisalRoutes: RouteRecordRaw = {
  path: 'appraisals',
  component: () => import('@/views/appraisals/AppraisalsLayout.vue'),
  children: [
    // The person's own appraisal: the step strip, "do now", goals, notes.
    { path: '', name: 'appraisal-home', component: () => import('@/views/appraisals/HomeView.vue') },
    { path: 'check-ins/:id', name: 'appraisal-check-in', component: () => import('@/views/appraisals/CheckInView.vue') },
    { path: 'review', name: 'appraisal-my-review', component: () => import('@/views/appraisals/ReviewView.vue') },
    // A manager's team: one to-do queue and everyone's quarter.
    { path: 'team', name: 'appraisal-team', component: () => import('@/views/appraisals/TeamView.vue') },
    { path: 'notes/:id', name: 'appraisal-notes', component: () => import('@/views/appraisals/NotesView.vue') },
    { path: 'people/:id', name: 'appraisal-person', component: () => import('@/views/appraisals/PersonView.vue') },
    { path: 'goals/:id', name: 'appraisal-goals', component: () => import('@/views/appraisals/SetGoalsView.vue') },
    { path: 'goals/:id/confirm', name: 'appraisal-confirm-goals', component: () => import('@/views/appraisals/ConfirmGoalsView.vue') },
    { path: 'reviews/:id', name: 'appraisal-review', component: () => import('@/views/appraisals/ReviewView.vue') },
    // HR: cycles, the fairness check, settings and role templates.
    { path: 'cycles', name: 'appraisal-cycles', component: () => import('@/views/appraisals/CyclesView.vue') },
    { path: 'cycles/:id', name: 'appraisal-cycle', component: () => import('@/views/appraisals/CycleView.vue') },
    { path: 'cycles/:id/fairness', name: 'appraisal-fairness', component: () => import('@/views/appraisals/FairnessView.vue') },
    { path: 'settings', name: 'appraisal-settings', component: () => import('@/views/appraisals/AppraisalSettingsView.vue') },
    { path: 'role-templates', name: 'appraisal-role-templates', component: () => import('@/views/appraisals/RoleTemplatesView.vue') },
  ],
}
