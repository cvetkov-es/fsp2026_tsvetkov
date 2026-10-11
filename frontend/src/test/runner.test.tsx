import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { AttemptState } from '../api/assessment'
import TestRunnerPage from '../pages/candidate/TestRunnerPage'

const base: AttemptState = { id: 'a1', target_grade: 'middle', express: false, status: 'in_progress', stage: 'phase1',
  n_answered: 0, phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null, result: null }
const item = { seq: 1, phase: 1, kind: 'number' as const, time_limit_s: 90, remaining_s: 42, presented_at: new Date().toISOString(),
  prompt: { text: '2 + 2 = ?', code: null, language: null, options: null, tables: [], steps: null, answer_hint: null } }

vi.mock('../api/assessment', async (orig) => ({
  ...(await orig<typeof import('../api/assessment')>()),
  getAttempt: vi.fn(async () => base),
  nextItem: vi.fn(async () => ({ ...base, item })),
  submitAnswer: vi.fn(async () => ({ ...base, stage: 'transition', n_answered: 6, phase2_total: 4,
    result: { decision: 'confirmed', phrase: 'Middle подтверждён · решено 6 из 6', reliability: 0.93, border: false, confident: false, express: false } })),
}))

describe('TestRunnerPage', () => {
  it('loads item, submits answer, shows transition screen', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/test/a1']}><Routes><Route path="/test/:attemptId" element={<TestRunnerPage />} /></Routes></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('2 + 2 = ?')).toBeInTheDocument()
    expect(screen.getByText('0:42')).toBeInTheDocument() // остаток по часам сервера, а не полный лимит
    await userEvent.type(screen.getByRole('textbox'), '4')
    await userEvent.click(screen.getByRole('button', { name: /ответить/i }))
    expect(await screen.findByText(/грейд подтверждён/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /продолжить/i })).toBeInTheDocument()
    expect(screen.getByText(/ещё 4 задания/i)).toBeInTheDocument()
  })
})
