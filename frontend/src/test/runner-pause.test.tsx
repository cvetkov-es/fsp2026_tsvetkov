import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as A from '../api/assessment'
import type { AttemptState } from '../api/assessment'
import { ApiError } from '../api/client'
import TestRunnerPage from '../pages/candidate/TestRunnerPage'

vi.mock('../api/assessment', async (orig) => ({
  ...(await orig<typeof import('../api/assessment')>()),
  getAttempt: vi.fn(), nextItem: vi.fn(), submitAnswer: vi.fn(), extendAttempt: vi.fn(),
}))

const base: AttemptState = { id: 'a1', target_grade: 'middle', express: false, status: 'in_progress', stage: 'phase1',
  n_answered: 0, phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null, result: null }
const item = { seq: 1, phase: 1, kind: 'number' as const, time_limit_s: 90, remaining_s: 90, presented_at: new Date().toISOString(),
  prompt: { text: '2 + 2 = ?', code: null, language: null, options: null, tables: [], steps: null, answer_hint: null } }

function renderRunner() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/test/a1']}><Routes><Route path="/test/:attemptId" element={<TestRunnerPage />} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe('TestRunnerPage pauses and edge states', () => {
  it('after an answer waits for the candidate before opening the next item', async () => {
    vi.mocked(A.getAttempt).mockResolvedValue(base)
    vi.mocked(A.nextItem).mockResolvedValue({ ...base, item })
    vi.mocked(A.submitAnswer).mockResolvedValue({ ...base, n_answered: 1 })
    renderRunner()
    await userEvent.type(await screen.findByRole('textbox'), '4')
    await userEvent.click(screen.getByRole('button', { name: /ответить/i }))
    const next = await screen.findByRole('button', { name: /следующее задание/i })
    expect(A.nextItem).toHaveBeenCalledTimes(1)
    await userEvent.click(next)
    expect(A.nextItem).toHaveBeenCalledTimes(2)
  })

  it('bank exhaustion explains that the attempt does not count', async () => {
    vi.mocked(A.getAttempt).mockResolvedValue({ ...base, status: 'incomplete', stage: 'incomplete', bank_exhausted: true, n_answered: 3 })
    renderRunner()
    expect(await screen.findByText(/Заданий не хватило, чтобы принять решение/)).toBeInTheDocument()
  })

  it('undecided express offers "later" and shows an error instead of crashing', async () => {
    vi.mocked(A.getAttempt).mockResolvedValue({ ...base, express: true, stage: 'awaiting_continue', n_answered: 8 })
    vi.mocked(A.extendAttempt).mockRejectedValue(new ApiError(409, 'not_extendable', 'Продолжить нельзя'))
    renderRunner()
    expect(await screen.findByRole('link', { name: /позже/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /продолжить тест/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Продолжить нельзя')
  })

  it('integrity events survive a failed submit and go with the retry', async () => {
    vi.mocked(A.getAttempt).mockResolvedValue({ ...base, item })
    vi.mocked(A.submitAnswer).mockRejectedValueOnce(new ApiError(503, 'unavailable', 'Сеть')).mockResolvedValue({ ...base, n_answered: 1 })
    renderRunner()
    await screen.findByText('2 + 2 = ?')
    document.dispatchEvent(new Event('paste'))
    await userEvent.click(screen.getByRole('button', { name: /ответить/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Сеть')
    await userEvent.click(screen.getByRole('button', { name: /ответить/i }))
    const events = vi.mocked(A.submitAnswer).mock.calls[1][3]
    expect(events.map((e) => e.type)).toEqual(['paste'])
  })

  it('order items hide the typed-answer hint because steps are picked by clicks', async () => {
    const order = { ...item, kind: 'order' as const, prompt: { ...item.prompt, steps: ['А', 'Б'], answer_hint: 'Номера всех шагов через пробел' } }
    vi.mocked(A.getAttempt).mockResolvedValue({ ...base, item: order })
    renderRunner()
    await screen.findByText('2 + 2 = ?')
    expect(screen.queryByText(/через пробел/)).not.toBeInTheDocument()
  })
})
