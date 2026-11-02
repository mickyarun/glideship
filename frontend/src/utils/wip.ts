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

// A stage's WIP limit. A limit of 0 or none means no limit; going over it
// is only ever a warning, never a block.

export function wipLimit(limit: number | null | undefined): number | null {
  return limit && limit > 0 ? limit : null
}

export function overWip(count: number, limit: number | null | undefined): boolean {
  const cap = wipLimit(limit)
  return cap !== null && count > cap
}
