import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { getAttempt, nextItem, submitAnswer, type AttemptState } from '../api/assessment'
import { ApiError } from '../api/client'
import TestRunnerPage from '../pages/candidate/TestRunnerPage'

const ai = { total: 12, time_left_s: 540, minutes: 10, sql_max_rows: 20, pass_accuracy: 0.75, pass_miss: 0.25 }
const base: AttemptState = { id: 'a1', target_grade: 'skill', skill_code: 'ai', ai, express: false, status: 'in_progress', stage: 'phase1',
  n_answered: 0, phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null, result: null }
const item = (seq: number) => ({ seq, phase: 1, kind: 'verdict' as const, time_limit_s: 540, remaining_s: 540, presented_at: new Date().toISOString(),
  prompt: { text: `Требование ${seq}`, code: 'def solve(xs):\n    return 0', language: 'python', options: null, tables: [], steps: null,
    answer_hint: null, input_classes: ['empty'], clarify: ['a', 'b', 'c', 'd'] } })

vi.mock('../api/assessment', async (orig) => ({
  ...(await orig<typeof import('../api/assessment')>()),
  getAttempt: vi.fn(async () => ({ ...base, n_answered: 3 })), // перезагрузка посреди попытки
  nextItem: vi.fn(async () => ({ ...base, n_answered: 3, item: item(4) })),
  submitAnswer: vi.fn(async () => ({ ...base, n_answered: 4 })),
}))

describe('TestRunnerPage for «Работа с ИИ»', () => {
  it('opens verdicts without pauses, numbers code lines and allows copying', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/test/a1']}><Routes><Route path="/test/:attemptId" element={<TestRunnerPage />} /></Routes></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('Требование 4')).toBeInTheDocument() // открылся сам, без «Следующее задание»
    expect(screen.getByText('Решение 4 из 12')).toBeInTheDocument()
    expect(screen.getByText(/ИИ разрешён/)).toBeInTheDocument()
    expect(screen.getByText('9:00')).toBeInTheDocument()
    const answer = screen.getByRole('button', { name: 'Ответить' })
    expect(answer).toBeDisabled()
    await userEvent.click(screen.getByLabelText('Верно'))
    await userEvent.click(screen.getByLabelText('Высокая'))
    await userEvent.click(answer)
    expect(submitAnswer).toHaveBeenCalledWith('a1', 4, { verdict: 'ok', confidence: 'high' }, expect.any(Array))
    expect(nextItem).toHaveBeenCalledTimes(2) // после ответа следующий вердикт открывается сразу
    expect(screen.queryByText('Ответ принят')).not.toBeInTheDocument()
  })

  it('shows the result when the shared timer ran out in a background tab', async () => {
    const finished: AttemptState = { ...base, status: 'completed', stage: 'finished', n_answered: 4, ai: { ...ai, time_left_s: null },
      result: { decision: 'not_confirmed', phrase: 'Работа с ИИ: не подтверждено · верных вердиктов 3 из 12 · время вышло', reliability: null,
        border: false, confident: false, express: false,
        ai: { passed: false, n: 12, answered: 4, correct: 3, accuracy: 0.25, miss_weighted: 0, false_reject: 0, minutes: 10, in_time: false } } }
    vi.mocked(getAttempt).mockResolvedValueOnce({ ...base, n_answered: 3 }).mockResolvedValueOnce(finished)
    vi.mocked(submitAnswer).mockRejectedValueOnce(new ApiError(409, 'attempt_closed', 'Попытка уже завершена'))
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/test/a1']}><Routes><Route path="/test/:attemptId" element={<TestRunnerPage />} /></Routes></MemoryRouter>
      </QueryClientProvider>,
    )
    await userEvent.click(await screen.findByLabelText('Верно'))
    await userEvent.click(screen.getByLabelText('Высокая'))
    await userEvent.click(screen.getByRole('button', { name: 'Ответить' }))
    expect(await screen.findByText(finished.result!.phrase)).toBeInTheDocument() // итог, а не «Попытка уже завершена»
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
