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
 * Who in an org room sees engineering detail.
 *
 * Board-only members (`boards:view` without `workspace:engineering`) may join
 * the Garden, but the room's state also carries engineering work: the
 * `@view()` fields of `MemberState` (the activity message, which names files)
 * and `AgentState` (who ran an agent, on which repository, doing what). Colyseus
 * sends a `@view()` field only to a client whose `StateView` holds that member
 * or agent, so an engineering client gets a view holding every member and
 * agent, and anyone else gets none: those fields reach them as empty strings.
 *
 * Members and agents come and go (snapshots, bridge events), so `sync` adds
 * the new ones to every engineering view; the room calls it each sim tick.
 * A field that changes is sent to a view as soon as the view holds its owner.
 */
import type { Client } from "colyseus"
import { StateView } from "@colyseus/schema"
import type { OrgRoomState } from "../schema/OrgRoomState"

export class EngineeringViews {
  private readonly views = new Set<StateView>()

  /** Give `client` the engineering view when `engineering`; otherwise none. */
  attach(client: Client, engineering: boolean, state: OrgRoomState): void {
    if (!engineering) return
    const view = new StateView()
    client.view = view
    this.views.add(view)
    this.syncView(view, state)
  }

  /** Forget a leaving client's view. */
  detach(client: Client): void {
    if (client.view) this.views.delete(client.view)
  }

  /** Add members and agents that appeared since the last call to every view. */
  sync(state: OrgRoomState): void {
    for (const view of this.views) this.syncView(view, state)
  }

  /** How many engineering clients there are. */
  get size(): number {
    return this.views.size
  }

  private syncView(view: StateView, state: OrgRoomState): void {
    for (const member of state.members.values()) {
      if (!view.has(member)) view.add(member)
    }
    for (const agent of state.agents.values()) {
      if (!view.has(agent)) view.add(agent)
    }
  }
}
