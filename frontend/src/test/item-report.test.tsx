import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { AttemptState } from '../api/assessment'
import ReportItem from '../components/test/ReportItem'
import TestRunnerPage from '../pages/candidate/TestRunnerPage'

const h = vi.hoisted(() => ({ report: vi.fn(async (_a: string, _s: number, _b: unknown) => ({ ok: true })), submit: vi.fn() }))
vi.mock('../api/complaints', async (orig) => ({ ...(await orig<typeof import('../api/complaints')>()), reportItem: (a: string, s: number, b: unknown) => h.report(a, s, b) }))

const base: AttemptState = { id: 'a1', target_grade: 'middle', express: false, status: 'in_progress', stage: 'phase1',
  n_answered: 0, phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null, result: null }
const item = { seq: 3, phase: 1, kind: 'number' as const, time_limit_s: 90, remaining_s: 42, presented_at: new Date().toISOString(),
  prompt: { text: '2 + 2 = ?', code: null, language: null, options: null, tables: [], steps: null, answer_hint: null } }
vi.mock('../api/assessment', async (orig) => ({
  ...(await orig<typeof import('../api/assessment')>()),
  getAttempt: vi.fn(async () => ({ ...base, item })),
  submitAnswer: (...a: unknown[]) => h.submit(...a),
}))

describe('report a problem in the task', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends the reason and the comment for this item and thanks the candidate', async () => {
    render(<ReportItem attemptId="a1" seq={3} />)
    await userEvent.click(screen.getByRole('button', { name: 'Сообщить о проблеме в задании' }))
    await userEvent.selectOptions(screen.getByLabelText('Что не так'), 'typo')
    await userEvent.type(screen.getByLabelText('Комментарий'), 'Опечатка в условии')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(h.report).toHaveBeenCalledWith('a1', 3, { reason: 'typo', comment: 'Опечатка в условии' })
    expect(await screen.findByText('Спасибо, модератор проверит')).toBeInTheDocument()
  })

  it('shows a server error and lets the candidate try again', async () => {
    h.report.mockRejectedValueOnce(new ApiError(409, 'already_reported', 'Вы уже сообщили о проблеме в этом задании'))
    render(<ReportItem attemptId="a1" seq={3} />)
    await userEvent.click(screen.getByRole('button', { name: 'Сообщить о проблеме в задании' }))
    await userEvent.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Вы уже сообщили о проблеме в этом задании')
  })

  it('is available under the task in the runner and does not touch the answer or the timer', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/test/a1']}>
      <Routes><Route path="/test/:attemptId" element={<TestRunnerPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('2 + 2 = ?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Сообщить о проблеме в задании' }))
    await userEvent.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(h.report).toHaveBeenCalledWith('a1', 3, { reason: 'wrong_key', comment: '' })
    expect(h.submit).not.toHaveBeenCalled()
    expect(screen.getByText('0:4', { exact: false })).toBeInTheDocument()  // таймер идёт, форма его не сбросила
  })
})
