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

/** "How appraisals work": the reader's side first, the cycle's dates, the rating words, and how it opens and closes. */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import '@/components/boards/__tests__/mountHelpers'
import type { GuideRead } from '@/types/appraisalSetup'

const apiGet = vi.fn()
vi.mock('@/services/api', () => ({ default: { get: apiGet } }))

const { default: AppraisalGuide } = await import('@/components/appraisals/AppraisalGuide.vue')
const { useAppraisalGuide } = await import('@/composables/useAppraisalGuide')
const { BANDS } = await import('@/utils/appraisalBands')
const { defaultRole, guideSteps } = await import('@/utils/appraisalGuide')
const { appraisalPlugins } = await import('./mountAppraisal')

const facts = (over: Partial<GuideRead> = {}): GuideRead => ({
  cycle_name: 'Q4 2026', review_period: 'quarterly', checkin_cadence: 'monthly', feedback_cadence: 'monthly',
  period_start: '2026-10-01', period_end: '2026-12-31', self_due: '2027-01-07', manager_due: '2027-01-14', ack_due: '2027-01-28',
  feedback_due_days: 5, min_goals: 3, max_goals: 6, reminder_offsets: [-3, 0, 2], ai_drafting: false, intro_note: '',
  is_manager: false, is_hr: false, ...over,
})
const settle = async () => {
  await flushPromises()
  await new Promise(r => setTimeout(r, 350))
}

async function mountGuide(guide: GuideRead) {
  apiGet.mockResolvedValue({ data: guide })
  const { plugins } = await appraisalPlugins()
  useAppraisalGuide().open.value = false
  // The facts are kept per person; a fresh person each time.
  useAppraisalGuide().guide.value = null
  const wrapper = mount(AppraisalGuide, { global: { plugins: plugins as never[] }, attachTo: document.body })
  return wrapper
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('the words', () => {
  it("opens on the reader's own side", () => {
    expect(defaultRole(facts({ is_hr: true, is_manager: true }))).toBe('hr')
    expect(defaultRole(facts({ is_manager: true }))).toBe('manager')
    expect(defaultRole(facts())).toBe('employee')
    expect(defaultRole(null)).toBe('employee')
  })

  it("gives the review deadline from the cycle, and leaves it out when there's none", () => {
    expect(guideSteps('employee', facts())[2].rest).toBe('when HR opens it, by Thu 7 Jan.')
    expect(guideSteps('employee', facts({ self_due: null }))[2].rest).toBe('when HR opens it.')
    expect(guideSteps('employee', facts())[0].rest).toBe('with your manager. They confirm 3 to 6.')
    expect(guideSteps('manager', facts())[1].rest).toBe('with Keep doing and Try next, within 5 working days of it being sent.')
  })

  it('says when notes come, as the cycle runs them, and reads a single goal count', () => {
    expect(guideSteps('employee', facts({ feedback_cadence: 'in_review' }))[1].rest).toBe("About 10 minutes. Your manager's notes come with your review.")
    expect(guideSteps('manager', facts({ feedback_cadence: 'in_review' }))[1].lead).toBe('Read each check-in')
    expect(guideSteps('manager', facts({ feedback_cadence: 'quarterly' }))[1].lead).toBe('Reply once a quarter')
    expect(guideSteps('manager', facts({ max_goals: 3 }))[0].rest).toBe('for each person, 3 each, by the goals date.')
    expect(guideSteps('employee', facts({ max_goals: 3 }))[0].rest).toBe('with your manager. They confirm 3.')
  })
})

describe('the dialog', () => {
  it('never opens by itself, only from its button', async () => {
    const wrapper = await mountGuide(facts())
    await settle()
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
    await wrapper.find('button').trigger('click')
    await settle()
    expect(document.body.querySelector('[role="dialog"]')).not.toBeNull()
  })

  it("shows the reader's side, the cycle, the five rating words, and switches side", async () => {
    const wrapper = await mountGuide(facts({ is_manager: true }))
    await wrapper.find('button').trigger('click')
    await settle()
    const text = document.body.textContent ?? ''
    expect(text).toContain('Q4 2026 · October to December')
    expect(text).toContain('Reply to each check-in')
    const words = [...document.body.querySelectorAll('.guide__bands li')].map(li => li.textContent?.trim())
    expect(words).toHaveLength(5)
    expect(words).toEqual(BANDS.map(b => b.label))
    const hr = [...document.body.querySelectorAll<HTMLButtonElement>('[aria-pressed]')].find(b => b.textContent?.trim() === 'HR')!
    expect(hr.getAttribute('aria-pressed')).toBe('false')
    // Every side is its own tab stop.
    expect([...document.body.querySelectorAll('[aria-pressed]')].map(b => b.getAttribute('tabindex'))).toEqual(['0', '0', '0'])
    hr.click()
    await settle()
    expect(hr.getAttribute('aria-pressed')).toBe('true')
    expect(document.body.textContent).toContain('Each cycle')
    // Closed and opened again, it starts on the reader's own side.
    useAppraisalGuide().open.value = false
    await settle()
    await wrapper.find('button').trigger('click')
    await settle()
    expect(document.body.textContent).toContain('Reply to each check-in')
  })

  it('closes with Got it or Esc, and gives focus back to its button', async () => {
    const wrapper = await mountGuide(facts())
    const opener = wrapper.find('button').element as HTMLElement
    for (const close of ['got-it', 'escape']) {
      opener.focus()
      opener.click()
      await settle()
      const dialog = document.body.querySelector('[role="dialog"]')!
      expect(dialog.getAttribute('aria-labelledby')).toBe(document.body.querySelector('.guide__title')?.id)
      if (close === 'got-it') {
        ;[...document.body.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent?.trim() === 'Got it')!.click()
      } else {
        document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
      }
      await settle()
      expect(useAppraisalGuide().open.value).toBe(false)
      expect(document.activeElement).toBe(opener)
    }
  })
})
