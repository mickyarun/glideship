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
 * Board activity in the Garden: a finished card cheers the actor's KayKit
 * character (the exact `Cheering` track, through the INTEGER `emote`
 * parameter, never touching the BOOLEAN `sitting`), handovers and
 * deliveries show a toast naming keys only when the event has them.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as pc from 'playcanvas'
import type { AssetLoader } from '../assets/AssetLoader'
import { LOCOMOTION_STATE_GRAPH } from '../characters/AnimUtils'
import { CharacterSystem, type CharacterSnapshot } from '../characters/CharacterSystem'
import { EMOTE } from '../characters/EmoteHolds'
import { ANIM_TRACK_MAP } from '../characters/KayKitCharacterFactory'
import { BoardActivityEffects, boardActivityMessage, CARD_DONE_CHEER_S, TOAST_GAP_MS } from './BoardActivityEffects'

const ACTOR = '22222222-2222-2222-2222-222222222222'

function fakeAnim() {
  return { setInteger: vi.fn(), setBoolean: vi.fn() }
}

/** A CharacterSystem holding one character with a recording anim component. */
function systemWith(userId: string) {
  const system = new CharacterSystem({} as AssetLoader)
  const anim = fakeAnim()
  const entity = {
    enabled: true, anim, getPosition: () => ({ x: 0, y: 0, z: 0 }), setPosition: vi.fn(), setLocalRotation: vi.fn(),
  }
  ;(system as unknown as { characters: unknown[] }).characters.push({ entity, memberId: userId, memberName: 'Asha' })
  return { system, anim, entity }
}

function snapshot(animState: string): CharacterSnapshot {
  return {
    userId: ACTOR, name: 'Asha', characterModel: '', level: 1, levelName: '', x: 0, y: 0, z: 0, yaw: 0,
    animState, labelName: '', labelMessage: '',
  }
}

function effects(system: CharacterSystem, overlay: HTMLElement | null = null, takeover: { userId: string; cheer: () => void } | null = null, now = () => 0) {
  return new BoardActivityEffects({ cheer: (id, s) => system.cheer(id, s), takeover: () => takeover, overlay: () => overlay }, now)
}

describe('board activity: card done', () => {
  it('drives the Cheer state, whose KayKit track is exactly Cheering', () => {
    expect(ANIM_TRACK_MAP.Cheer).toBe('Cheering')
    const toCheer = LOCOMOTION_STATE_GRAPH.layers[0].transitions.find(t => t.from === 'Idle' && t.to === 'Cheer')
    expect(toCheer?.conditions).toEqual([{ parameterName: 'emote', predicate: pc.ANIM_EQUAL_TO, value: EMOTE.cheer }])
    expect(LOCOMOTION_STATE_GRAPH.parameters.emote.type).toBe(pc.ANIM_PARAMETER_INTEGER)
    expect(LOCOMOTION_STATE_GRAPH.parameters.sitting.type).toBe(pc.ANIM_PARAMETER_BOOLEAN)
  })

  it('cheers on the actor with the integer emote, and never sets sitting', () => {
    const { system, anim } = systemWith(ACTOR)
    effects(system).handle({ kind: 'card_done', actor_id: ACTOR })
    expect(anim.setInteger).toHaveBeenCalledWith('emote', EMOTE.cheer)
    expect(anim.setInteger.mock.calls.some(([name]) => name === 'sitting')).toBe(false)
    expect(anim.setBoolean).not.toHaveBeenCalled()
  })

  it('keeps cheering through idle snapshots, then hands back to the server', () => {
    const { system, anim } = systemWith(ACTOR)
    system.updateFromSnapshot(snapshot('idle'))
    effects(system).handle({ kind: 'card_done', actor_id: ACTOR })
    anim.setInteger.mockClear()
    system.updateFromSnapshot(snapshot('idle'))
    expect(anim.setInteger).toHaveBeenCalledWith('emote', EMOTE.cheer)
    expect(anim.setBoolean).toHaveBeenCalledWith('sitting', false)
    anim.setInteger.mockClear()
    system.update(CARD_DONE_CHEER_S + 0.1)
    expect(anim.setInteger).toHaveBeenCalledWith('emote', EMOTE.none)
  })

  it('lets the server win when it moves the character, and skips a walking or absent one', () => {
    const { system, anim } = systemWith(ACTOR)
    effects(system).handle({ kind: 'card_done', actor_id: ACTOR })
    system.updateFromSnapshot(snapshot('walk'))
    expect(anim.setInteger).toHaveBeenLastCalledWith('emote', EMOTE.none)
    anim.setInteger.mockClear()
    expect(system.cheer(ACTOR, CARD_DONE_CHEER_S)).toBe(false)
    expect(anim.setInteger).not.toHaveBeenCalled()
    expect(system.cheer('someone-else', CARD_DONE_CHEER_S)).toBe(false)
    effects(system).handle({ kind: 'card_done', actor_id: null })
    expect(anim.setInteger).not.toHaveBeenCalled()
  })

  it('plays the local takeover emote when the actor is the one in control', () => {
    const { system, anim } = systemWith(ACTOR)
    const cheer = vi.fn()
    effects(system, null, { userId: ACTOR, cheer }).handle({ kind: 'card_done', actor_id: ACTOR })
    expect(cheer).toHaveBeenCalledOnce()
    expect(anim.setInteger).not.toHaveBeenCalled()
  })
})

describe('board activity: handover and delivery', () => {
  let overlay: HTMLElement
  beforeEach(() => {
    vi.useFakeTimers()
    overlay = document.createElement('div')
  })
  afterEach(() => vi.useRealTimers())

  it('names the card or board only when the event carries its key, never a title', () => {
    expect(boardActivityMessage({ kind: 'handover', actor_id: ACTOR, board_key: 'OPS', card_key: 'OPS-12' })).toBe('OPS-12 handed over to Delivery')
    expect(boardActivityMessage({ kind: 'handover', actor_id: ACTOR, board_key: 'OPS' })).toBe('A OPS card handed over to Delivery')
    expect(boardActivityMessage({ kind: 'handover', actor_id: ACTOR })).toBe('A card handed over to Delivery')
    expect(boardActivityMessage({ kind: 'bud_delivered', actor_id: null, board_key: 'OPS', card_key: 'OPS-12' })).toBe('OPS-12 delivered')
    expect(boardActivityMessage({ kind: 'bud_delivered', actor_id: null })).toBe('Board work delivered')
    expect(boardActivityMessage({ kind: 'card_done', actor_id: ACTOR })).toBeNull()
  })

  it('shows one toast with confetti, and no more than one per gap', () => {
    const { system } = systemWith(ACTOR)
    let t = 0
    const fx = effects(system, overlay, null, () => t)
    fx.handle({ kind: 'handover', actor_id: ACTOR, board_key: 'OPS', card_key: 'OPS-12' })
    expect(overlay.textContent).toBe('OPS-12 handed over to Delivery')
    expect(overlay.children.length).toBeGreaterThan(1)
    t = TOAST_GAP_MS - 1
    fx.handle({ kind: 'bud_delivered', actor_id: null })
    expect(overlay.textContent).toBe('OPS-12 handed over to Delivery')
    vi.runAllTimers()
    expect(overlay.children.length).toBe(0)
    t = TOAST_GAP_MS * 2
    fx.handle({ kind: 'bud_delivered', actor_id: null })
    expect(overlay.textContent).toBe('Board work delivered')
  })
})
