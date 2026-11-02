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

// Keeping a long menu clear of its own button. Vuetify shifts a menu that
// doesn't fit back into the window, which can lay its items over the
// button, so a quick double click picks one. Measured as it opens, the menu
// opens below its button (or above, when there's more room there), only as
// tall as that room and scrolling past it; and an item ignores the second
// click of a double click, which is the opening gesture landing, not a pick.

import { ref } from 'vue'
import { MENU_MIN_ROOM_PX, MENU_OFFSET_PX, MENU_VIEWPORT_MARGIN_PX } from '@/constants/layout'

type Side = 'bottom end' | 'top end'

export function useMenuRoom() {
  const location = ref<Side>('bottom end')
  const maxHeight = ref<number | undefined>(undefined)

  /** Call as the menu opens, with its button. */
  function opened(button: Element | null | undefined): void {
    if (!button) return
    const box = button.getBoundingClientRect()
    const gap = MENU_OFFSET_PX + MENU_VIEWPORT_MARGIN_PX
    const below = window.innerHeight - box.bottom - gap
    const above = box.top - gap
    const down = below >= MENU_MIN_ROOM_PX || below >= above
    location.value = down ? 'bottom end' : 'top end'
    maxHeight.value = Math.max(0, Math.floor(down ? below : above))
  }

  /**
   * Whether a click on an item is a real pick. A deliberate pick, by mouse
   * or keyboard, is a single click; the second click of a double click on
   * the button is the opening gesture landing on the menu.
   */
  function picking(event: Event | undefined): boolean {
    return !(event instanceof MouseEvent && event.detail > 1)
  }

  return { location, maxHeight, offset: MENU_OFFSET_PX, opened, picking }
}
