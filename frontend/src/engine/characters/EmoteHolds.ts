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
 * EmoteHolds — a client-side emote played on a server-driven character for
 * a few seconds (a cheer when its member finishes a card).
 *
 * Server snapshots set the `emote` parameter on every state change, which
 * would cancel a client-side cheer on the next one. A hold wins over the
 * snapshot until it runs out; then the character goes back to whatever the
 * server says. Time runs on the frame's `dt`, so it pauses with the scene.
 */

/**
 * `emote` values in LOCOMOTION_STATE_GRAPH (AnimUtils.ts): an INTEGER
 * parameter on every Garden character (all KayKit), whose states play the
 * tracks in KayKitCharacterFactory's ANIM_TRACK_MAP.
 */
export const EMOTE = { none: 0, wave: 1, cheer: 2, defeat: 3 } as const
export type EmoteId = (typeof EMOTE)[keyof typeof EMOTE]

export class EmoteHolds {
  private readonly holds = new Map<string, { emote: EmoteId; left: number }>()

  /** Play ``emote`` on ``userId`` for ``seconds`` (a newer hold replaces an older one). */
  hold(userId: string, emote: EmoteId, seconds: number): void {
    this.holds.set(userId, { emote, left: seconds })
  }

  /** The emote a hold keeps playing on ``userId``, or null with none. */
  current(userId: string): EmoteId | null {
    return this.holds.get(userId)?.emote ?? null
  }

  /** Advance every hold by ``dt`` seconds; returns the users whose hold just ran out. */
  tick(dt: number): string[] {
    const ended: string[] = []
    for (const [userId, h] of this.holds) {
      h.left -= dt
      if (h.left <= 0) {
        this.holds.delete(userId)
        ended.push(userId)
      }
    }
    return ended
  }

  drop(userId: string): void {
    this.holds.delete(userId)
  }

  clear(): void {
    this.holds.clear()
  }
}
