import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TasksPage from '../pages/employer/TasksPage'

const h = vi.hoisted(() => ({
  trust: 'L1',
  create: vi.fn(async (_body: unknown) => ({ id: 't9' })),
  evaluate: vi.fn(async (_id: string, _body: unknown) => ({})),
  hint: vi.fn(async (_id: string) => ({ id: 's1', llm_hint: { fits: 'partly', summary: 'Учтены не все граничные случаи' } })),
}))
vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getCompany: vi.fn(async () => ({ id: 'k1', name: 'Корп', description: null, industry: null, contacts: {}, trust_level: h.trust })),
  listNeeds: vi.fn(async () => [{ id: 'n1', title: 'Бэкенд', status: 'active' }]),
}))
vi.mock('../api/tasks', async (orig) => ({
  ...(await orig<typeof import('../api/tasks')>()),
  getTaskLimits: vi.fn(async () => ({ text_max: 2000, ttl_days: 14 })),
  getCompanyTasks: vi.fn(async () => [{ id: 't1', title: 'Посчитать p95', specialization: 'backend', deadline: '2026-10-16T12:00:00Z', status: 'open', submissions: 2, pending: 1 }]),
  getTaskSubmissions: vi.fn(async () => ({
    task: { id: 't1', title: 'Посчитать p95', text: 'Дан лог', reference_answer: '42', answer_kind: 'number', deadline: '2026-10-16T12:00:00Z', status: 'open' },
    items: [{ id: 's1', alias: 'B-M-AAAA', ref: 'aaaa1111', answer: 'Мой ответ', auto_correct: true, verdict: null, comment: null, llm_hint: null, created_at: '2026-10-09T10:00:00Z' }],
  })),
  createTask: (body: unknown) => h.create(body),
  evaluateSubmission: (id: string, body: unknown) => h.evaluate(id, body),
  hintSubmission: (id: string) => h.hint(id),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><TasksPage /></MemoryRouter></QueryClientProvider>)

describe('employer TasksPage', () => {
  beforeEach(() => { vi.clearAllMocks(); h.trust = 'L1' })

  it('hides the form for L0 and explains the trust level', async () => {
    h.trust = 'L0'
    setup()
    expect(await screen.findByText(/Публиковать задачи можно с уровня доверия L1/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Опубликовать задачу' })).not.toBeInTheDocument()
  })

  it('publishes a task with the deadline as an ISO datetime and a counter from the server limit', async () => {
    setup()
    await userEvent.type(await screen.findByLabelText('Название задачи'), 'Новая задача')
    await userEvent.type(screen.getByLabelText('Текст задачи'), 'Описание задачи')
    expect(screen.getByText('15 / 2000')).toBeInTheDocument()
    const d = new Date(Date.now() + 3 * 86_400_000)
    fireEvent.change(screen.getByLabelText('Срок'), { target: { value: d.toISOString().slice(0, 10) } })
    await userEvent.click(screen.getByRole('button', { name: 'Опубликовать задачу' }))
    expect(h.create).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Новая задача', specialization: 'backend', text: 'Описание задачи', deadline: expect.stringMatching(/^\d{4}-\d\d-\d\dT.*Z$/),
    }))
  })

  it('shows the submissions with the autocheck, evaluates and asks the model for advice only', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Решения (2, ждут проверки: 1)' }))
    expect(await screen.findByText('B-M-AAAA')).toBeInTheDocument()
    expect(screen.getByText(/совпадает с эталоном/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Подсказка ИИ' }))
    expect(await screen.findByText(/подсказка ИИ, решаете вы/)).toBeInTheDocument()
    expect(screen.getByText(/Учтены не все граничные случаи/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Принять' }))
    expect(h.evaluate).toHaveBeenCalledWith('s1', { verdict: 'accepted', comment: '' })
  })
})
