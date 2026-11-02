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
 * Engineering detail in the org room: an engineering member's client decodes
 * the activity message and agent work (repository, actor, message); a
 * board-only member's client decodes the same room with those fields empty,
 * on join and for members and agents that appear later.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { Decoder } from "@colyseus/schema"
import { ClientState, SchemaSerializer, type Client } from "colyseus"
import { AgentState } from "../schema/AgentState"
import { MemberState } from "../schema/MemberState"
import { OrgRoomState } from "../schema/OrgRoomState"
import { joinRoom } from "../testing/join"
import { OrgRoom } from "./OrgRoom"

const ORG = "5c0e6f8a-2b3d-4e5f-8a6b-7c8d9e0f1a2b"
// Bytes Colyseus puts before the encoded state (the protocol code).
const PROTOCOL_BYTES = 1

interface Viewer {
  client: Client
  decoder: Decoder<OrgRoomState>
}

let room: OrgRoom

function viewer(sessionId: string): Viewer {
  const decoder = new Decoder(new OrgRoomState())
  const client = {
    sessionId,
    state: ClientState.JOINED,
    userData: undefined,
    send: vi.fn(),
    raw: (bytes: Uint8Array) => decoder.decode(bytes, { offset: PROTOCOL_BYTES }),
  } as unknown as Client
  return { client, decoder }
}

function member(userId: string, message: string): MemberState {
  const m = new MemberState()
  m.userId = userId
  m.name = "Ana"
  m.labelName = "Ana"
  m.labelMessage = message
  return m
}

function agent(agentId: string, repoName: string): AgentState {
  const a = new AgentState()
  a.agentId = agentId
  a.skillName = "Code review"
  a.actorName = "Ana"
  a.repoName = repoName
  a.message = `Reviewing ${repoName}`
  return a
}

function verifyAs(engineering: boolean): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      const { token } = JSON.parse(String(init?.body)) as { token: string }
      return Response.json({ valid: true, user_id: token, org_id: ORG, name: token, engineering })
    }),
  )
}

async function join(who: Viewer, engineering: boolean): Promise<void> {
  verifyAs(engineering)
  await joinRoom(room, who.client, { orgId: ORG, token: who.client.sessionId })
}

beforeEach(() => {
  vi.spyOn(console, "log").mockImplementation(() => undefined)
  vi.spyOn(console, "warn").mockImplementation(() => undefined)
  room = new OrgRoom()
  room.setState(new OrgRoomState())
  room.state.orgId = ORG
  room.state.members.set("u1", member("u1", "Editing src/billing/ledger.ts"))
  room.state.agents.set("t1", agent("t1", "payments-api"))
})

afterEach(() => {
  room.clock.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("engineering detail in the org room", () => {
  it("reaches only the engineering client, on join and for later arrivals", async () => {
    const engineer = viewer("eng")
    const boardUser = viewer("board")
    await join(engineer, true)
    await join(boardUser, false)
    expect(engineer.client.view).toBeDefined()
    expect(boardUser.client.view).toBeUndefined()

    const serializer = new SchemaSerializer<OrgRoomState>()
    serializer.reset(room.state)
    for (const who of [engineer, boardUser]) {
      who.client.raw(serializer.getFullState(who.client))
    }

    const seen = (who: Viewer) => who.decoder.state
    expect(seen(engineer).members.get("u1")?.labelMessage).toBe("Editing src/billing/ledger.ts")
    expect(seen(engineer).agents.get("t1")?.repoName).toBe("payments-api")
    const quiet = seen(boardUser)
    expect(quiet.members.get("u1")?.labelName).toBe("Ana")
    expect(quiet.members.get("u1")?.labelMessage).toBe("")
    expect(quiet.agents.get("t1")?.skillName).toBe("Code review")
    expect([quiet.agents.get("t1")?.repoName, quiet.agents.get("t1")?.actorName]).toEqual([
      "",
      "",
    ])
    expect(quiet.agents.get("t1")?.message).toBe("")

    room.state.agents.set("t2", agent("t2", "ledger-service"))
    room.state.members.get("u1")!.labelMessage = "Committed fix in ledger-service"
    room.engineeringViews.sync(room.state)
    serializer.applyPatches([engineer.client, boardUser.client])

    expect(seen(engineer).agents.get("t2")?.repoName).toBe("ledger-service")
    expect(seen(engineer).members.get("u1")?.labelMessage).toBe("Committed fix in ledger-service")
    expect(quiet.agents.get("t2")?.skillName).toBe("Code review")
    expect(quiet.agents.get("t2")?.repoName).toBe("")
    expect(quiet.members.get("u1")?.labelMessage).toBe("")
  })

  it("forgets a leaving engineering client's view", async () => {
    const engineer = viewer("eng")
    await join(engineer, true)
    expect(room.engineeringViews.size).toBe(1)
    room.onLeave(engineer.client)
    expect(room.engineeringViews.size).toBe(0)
  })

  it("treats a verification without the flag as not engineering", async () => {
    const who = viewer("old-backend")
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ valid: true, user_id: "u9", org_id: ORG, name: "Old" })),
    )
    await joinRoom(room, who.client, { orgId: ORG, token: "jwt" })
    expect(who.client.view).toBeUndefined()
  })
})
