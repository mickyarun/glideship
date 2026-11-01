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
 * Tells the newest of overlapping loads from older ones. Each call to the
 * returned `begin` starts a load and gives back its `latest()` check, which
 * stays true only until the next `begin`. A load whose reply lands after a
 * newer one has started checks `latest()` and drops it, so a slow, older
 * reply never replaces the newer one on screen.
 *
 *   const beginBoardLoad = latestCall()
 *   async function fetchBoard() {
 *     const latest = beginBoardLoad()
 *     const { data } = await api.get(...)
 *     if (latest()) board.value = data
 *   }
 *
 * Calling `begin` without loading anything also works: it cancels whatever
 * is in flight, as clearing the data on sign-out needs.
 */
export function latestCall(): () => () => boolean {
  let newest = 0
  return () => {
    const mine = ++newest
    return () => mine === newest
  }
}
