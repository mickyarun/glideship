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
 * board_activity: the backend's Garden events for board work are checked
 * and re-broadcast to the org room's clients, with nothing extra passed on.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { OrgRoomState } from "../schema/OrgRoomState"
import { parseBoardActivityEvent } from "../sim/BoardActivity"
import { OrgRoom } from "./OrgRoom"

const ACTOR = "0b6f8e2a-1c3d-4e5f-8a9b-0c1d2e3f4a5b"

let room: OrgRoom

beforeEach(() => {
  vi.spyOn(console, "log").mockImplementation(() => undefined)
  vi.spyOn(console, "warn").mockImplementation(() => undefined)
  room = new OrgRoom()
  room.setState(new OrgRoomState())
  room.state.orgId = "org-a"
})

afterEach(() => {
  room.clock.clear()
  vi.restoreAllMocks()
})

describe("parseBoardActivityEvent", () => {
  it("keeps an org-visible board's keys", () => {
    expect(
      parseBoardActivityEvent({
        kind: "card_done",
        actor_id: ACTOR,
        board_key: "SEO",
        card_key: "SEO-14",
        card_title: "should never pass",
      }),
    ).toEqual({ kind: "card_done", actor_id: ACTOR, board_key: "SEO", card_key: "SEO-14" })
  })

  it("carries only kind and actor for a members-only board", () => {
    expect(parseBoardActivityEvent({ kind: "handover", actor_id: ACTOR })).toEqual({
      kind: "handover",
      actor_id: ACTOR,
    })
  })

  it("accepts a delivery with no actor and drops keys that aren't keys", () => {
    expect(
      parseBoardActivityEvent({ kind: "bud_delivered", actor_id: null, board_key: "<b>", card_key: "X-1" }),
    ).toEqual({ kind: "bud_delivered", actor_id: null })
    expect(
      parseBoardActivityEvent({ kind: "card_done", actor_id: null, board_key: "OPS", card_key: "OPS-x" }),
    ).toEqual({ kind: "card_done", actor_id: null, board_key: "OPS" })
  })

  it.each([
    ["unknown kind", { kind: "card_moved", actor_id: ACTOR }],
    ["missing actor", { kind: "card_done" }],
    ["bad actor", { kind: "card_done", actor_id: "alice" }],
    ["non-object", "card_done"],
    ["null", null],
  ])("rejects a payload with %s", (_label, raw) => {
    expect(parseBoardActivityEvent(raw)).toBeNull()
  })
})

describe("board_activity bridge event", () => {
  it("re-broadcasts the checked event to the room", () => {
    const broadcast = vi.spyOn(room, "broadcast").mockImplementation(() => undefined)
    room.handleBridgeEvent("board_activity", { kind: "card_done", actor_id: ACTOR, extra: 1 })
    expect(broadcast).toHaveBeenCalledWith("board_activity", { kind: "card_done", actor_id: ACTOR })
  })

  it("drops a malformed payload without broadcasting", () => {
    const broadcast = vi.spyOn(room, "broadcast").mockImplementation(() => undefined)
    room.handleBridgeEvent("board_activity", { kind: "nope" })
    expect(broadcast).not.toHaveBeenCalled()
    expect(room.state.agents.size).toBe(0)
  })
})
