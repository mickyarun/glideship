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

// Load a column's next page as its bottom scrolls into view: an element
// at the end of the card list is watched inside the column's own scroll
// box (or the window, when the root is null). Where IntersectionObserver is missing, the column's Load more
// button still works.

import { onBeforeUnmount, watch, type Ref } from 'vue'

export function useLoadMoreSentinel(
  sentinel: Ref<HTMLElement | null>,
  root: Readonly<Ref<HTMLElement | null>>,
  onVisible: () => void,
): void {
  let observer: IntersectionObserver | null = null

  function stop(): void {
    observer?.disconnect()
    observer = null
  }

  watch(
    [sentinel, root],
    ([el, box]) => {
      stop()
      if (!el || typeof IntersectionObserver === 'undefined') return
      observer = new IntersectionObserver(
        entries => {
          if (entries.some(e => e.isIntersecting)) onVisible()
        },
        { root: box, rootMargin: '0px 0px 120px 0px' },
      )
      observer.observe(el)
    },
    { immediate: true, flush: 'post' },
  )

  onBeforeUnmount(stop)
}
