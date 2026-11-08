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
 * People-workspace routes, open to every signed-in member regardless of
 * role. Leave, WFH and employee records land here.
 */
import type { RouteRecordRaw } from 'vue-router'

export const peopleRoutes: RouteRecordRaw[] = [
  {
    path: 'leave',
    name: 'leave',
    component: () => import('@/views/leave/LeaveHomeView.vue'),
  },
  {
    path: 'leave/team',
    name: 'leave-team',
    component: () => import('@/views/leave/TeamCalendarView.vue'),
  },
  {
    // Everyone sees their office's holidays; HR can switch offices.
    path: 'leave/holidays',
    name: 'leave-holidays',
    component: () => import('@/views/leave/HolidaysView.vue'),
  },
  {
    // Managers see their reports' requests; holders of leave:approve see
    // everyone's. The API decides what's in the queue.
    path: 'leave/approvals',
    name: 'leave-approvals',
    component: () => import('@/views/leave/LeaveApprovalsView.vue'),
  },
  {
    // HR and the owner (leave:reports) see everyone; managers their direct
    // reports. The API decides; the view explains when there's nothing.
    path: 'leave/reports',
    name: 'leave-reports',
    component: () => import('@/views/leave/LeaveReportsView.vue'),
  },
  {
    // Everyone: their own check-ins. The API decides what each person sees.
    path: 'appraisals',
    name: 'appraisal-my-month',
    component: () => import('@/views/appraisals/MyMonthView.vue'),
  },
  {
    path: 'appraisals/team',
    name: 'appraisal-team',
    component: () => import('@/views/appraisals/TeamCheckInsView.vue'),
  },
  {
    path: 'appraisals/check-ins/:id',
    name: 'appraisal-check-in',
    component: () => import('@/views/appraisals/CheckInView.vue'),
  },
  {
    // The manager writes; the person and HR read. The API decides.
    path: 'appraisals/feedback/:id',
    name: 'appraisal-feedback',
    component: () => import('@/views/appraisals/FeedbackView.vue'),
  },
  {
    // HR only (appraisals:manage); the API refuses everyone else.
    path: 'appraisals/cycles',
    name: 'appraisal-cycles',
    component: () => import('@/views/appraisals/CyclesView.vue'),
  },
  {
    path: 'appraisals/cycles/:id',
    name: 'appraisal-cycle',
    component: () => import('@/views/appraisals/CycleView.vue'),
  },
  {
    path: 'appraisals/settings',
    name: 'appraisal-settings',
    component: () => import('@/views/appraisals/AppraisalSettingsView.vue'),
  },
  {
    path: 'appraisals/role-templates',
    name: 'appraisal-role-templates',
    component: () => import('@/views/appraisals/RoleTemplatesView.vue'),
  },
  {
    // The person, their managers and HR; the API decides what each sees.
    path: 'appraisals/goals/:id',
    name: 'appraisal-goals',
    component: () => import('@/views/appraisals/GoalsView.vue'),
  },
  {
    // The caller's latest review.
    path: 'appraisals/review',
    name: 'appraisal-my-review',
    component: () => import('@/views/appraisals/ReviewView.vue'),
  },
  {
    path: 'appraisals/reviews/:id',
    name: 'appraisal-review',
    component: () => import('@/views/appraisals/ReviewView.vue'),
  },
  {
    path: 'settings/leave',
    name: 'settings-leave',
    meta: { permission: 'leave:configure' },
    component: () => import('@/views/settings/SettingsLeave.vue'),
  },
  {
    path: 'settings/offices',
    name: 'settings-offices',
    meta: { permission: 'employees:manage' },
    component: () => import('@/views/settings/SettingsOffices.vue'),
  },
  {
    path: 'settings/celebrations',
    name: 'settings-celebrations',
    // HR (owns the dates) or admins/the owner (own the channel). Any-of,
    // matching the backend; the channel itself is admin/owner-only.
    meta: { permission: ['employees:manage', 'org:edit_settings'] },
    component: () => import('@/views/settings/SettingsCelebrations.vue'),
  },
  {
    path: 'people',
    name: 'employees',
    meta: { permission: 'employees:view' },
    component: () => import('@/views/people/EmployeeDirectoryView.vue'),
  },
  {
    path: 'people/:userId',
    name: 'employee-profile',
    // The page itself decides what to show: the API returns 403 unless the
    // caller holds employees:view or is looking at their own record.
    component: () => import('@/views/people/EmployeeProfileView.vue'),
  },
  {
    // "My details": the caller's own employee record.
    path: 'me/profile',
    name: 'my-details',
    component: () => import('@/views/people/EmployeeProfileView.vue'),
  },
  {
    // Self-service per-user notification opt-outs. No permission gate —
    // any authenticated member manages their own Slack DM preferences
    // via /v1/me/notification-preferences.
    path: 'profile/notifications',
    name: 'profile-notifications',
    component: () => import('@/views/profile/NotificationSettings.vue'),
  },
]
