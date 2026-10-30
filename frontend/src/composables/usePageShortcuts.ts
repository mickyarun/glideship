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

// Whether single-key page shortcuts (like B for the board switcher) may
// fire. A route opts out with ``meta.shortcuts: false``; a surface that
// takes the keyboard for itself (the Garden canvas) suspends them while
// it's mounted.

import { onMounted, onUnmounted, ref } from 'vue'

const suspended = ref(0)

/** Call in a component that owns the keyboard while it's on screen. */
export function useSuspendPageShortcuts(): void {
  onMounted(() => {
    suspended.value++
  })
  onUnmounted(() => {
    suspended.value = Math.max(0, suspended.value - 1)
  })
}

export function pageShortcutsSuspended(): boolean {
  return suspended.value > 0
}
