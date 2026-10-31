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

// A stand-in for useJobSocket that records the jobs followed, so a test
// can play a job's progress, completion or failure.

import { vi } from 'vitest'
import type { TrackerCallbacks } from '@/composables/useRealtimeTracker'
import type { JobStatusRead } from '@/types'

/** Jobs the wizard followed, newest last, with the callbacks it gave. */
export const tracked: { id: string; cbs: TrackerCallbacks<JobStatusRead> }[] = []

/** Every stand-in's stopTracking, to check the wizard let go of its job. */
export const stopTracking = vi.fn()

export function jobSocketStub() {
  return {
    status: { value: null },
    isActive: { value: false },
    startTracking: (id: string, cbs: TrackerCallbacks<JobStatusRead>) => tracked.push({ id, cbs }),
    stopTracking,
  }
}
