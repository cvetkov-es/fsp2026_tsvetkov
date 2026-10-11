import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { getAttempt, submitAnswer, type AttemptState } from '../api/assessment'
import { FocusModeContext } from '../components/focus-mode'
import TestRunnerPage from '../pages/candidate/TestRunnerPage'

const base: AttemptState = { id: 'a1', target_grade: 'middle', express: false, status: 'in_progress', stage: 'phase1',
  n_answered: 2, phase2_total: 0, phase2_answered: 0, bank_exhausted: false, item: null, result: null }
const item = { seq: 3, phase: 1, kind: 'choice' as const, time_limit_s: 90, remaining_s: 80, presented_at: new Date().toISOString(),
  prompt: { text: 'Какое значение n вернёт запрос для Казани?', code: 'SELECT 1;', language: 'sql', options: ['0', '1', '2', 'NULL'],
    tables: [{ name: 'customers', columns: ['id', 'city'], rows: [[1, 'Казань']] }], steps: null, answer_hint: null } }

vi.mock('../api/assessment', async (orig) => ({
  ...(await orig<typeof import('../api/assessment')>()),
  getAttempt: vi.fn(),
  nextItem: vi.fn(),
  submitAnswer: vi.fn(),
}))

const show = (setFocus: (on: boolean) => void = () => {}) => render(
  <FocusModeContext.Provider value={setFocus}><QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={['/test/a1']}><Routes><Route path="/test/:attemptId" element={<TestRunnerPage />} /></Routes></MemoryRouter>
  </QueryClientProvider></FocusModeContext.Provider>)

describe('Тест в фокус-режиме', () => {
  it('covers the site header, shows honest progress and no way out of an open item', async () => {
    vi.mocked(getAttempt).mockResolvedValue({ ...base, item })
    show()
    expect(await screen.findByText('Какое значение n вернёт запрос для Казани?')).toBeInTheDocument()
    expect(screen.getByTestId('focus-shell')).toHaveClass('fixed', 'inset-0')
    expect(screen.getByText('Тест на Middle · полный тест')).toBeInTheDocument()
    const bar = screen.getByRole('progressbar', { name: 'Пройдено заданий' })
    expect(bar).toHaveAttribute('aria-valuetext', 'Пройдено заданий: 2')
    expect(bar).not.toHaveAttribute('aria-valuenow')       // длина адаптивного теста заранее неизвестна: процент не объявляем
    expect(bar.children[0]).toHaveClass('min-w-0', 'flex-1')  // до 16 делений сжимаются, а не уходят за край на 390 px
    expect(bar.children).toHaveLength(3)                   // два пройденных и текущее
    expect(screen.queryByRole('link', { name: /в кабинет/i })).not.toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('SELECT 1;')).toBeInTheDocument()
  })

  it('hides the site header from keyboard and screen readers while the shell is open', async () => {
    vi.mocked(getAttempt).mockResolvedValue({ ...base, item })
    const setFocus = vi.fn()
    const { unmount } = show(setFocus)
    await screen.findByTestId('focus-shell')
    await waitFor(() => expect(setFocus).toHaveBeenLastCalledWith(true))  // эффект может отработать после появления разметки
    unmount()
    expect(setFocus).toHaveBeenLastCalledWith(false)
  })

  it('submits by itself when the timer runs out', async () => {
    vi.mocked(getAttempt).mockResolvedValue({ ...base, item: { ...item, remaining_s: 0 } })
    vi.mocked(submitAnswer).mockResolvedValue({ ...base, n_answered: 3 })
    show()
    await waitFor(() => expect(submitAnswer).toHaveBeenCalled())
  })

  it('between items the candidate may leave', async () => {
    vi.mocked(getAttempt).mockResolvedValue({ ...base, n_answered: 1 })
    show()
    expect(await screen.findByRole('button', { name: /следующее задание/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← В кабинет' })).toHaveAttribute('href', '/')
  })

  it('the AI skill knows its length and shows the whole bar', async () => {
    const ai = { total: 12, time_left_s: 540, minutes: 40, sql_max_rows: 20, pass_accuracy: 0.75, pass_miss: 0.25 }
    vi.mocked(getAttempt).mockResolvedValue({ ...base, target_grade: 'skill', skill_code: 'ai', ai, n_answered: 3, item: { ...item, kind: 'number' as const } })
    show()
    const bar = await screen.findByRole('progressbar', { name: 'Пройдено заданий' })
    expect(bar).toHaveAttribute('aria-valuemax', '12')
    expect(bar.children).toHaveLength(12)
    expect(screen.getByText('Работа с ИИ')).toBeInTheDocument()
    expect(screen.getByText('Решение 4 из 12')).toBeInTheDocument()
  })
})
