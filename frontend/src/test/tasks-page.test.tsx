import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import TasksPage from '../pages/candidate/TasksPage'

const h = vi.hoisted(() => ({
  submit: vi.fn(async (_id: string, _answer: string) => ({ status: 'pending', comment: null })),
  complain: vi.fn(async (_id: string, _comment: string) => ({ ok: true })),
}))
const company = { name: 'Корп', trust_level: 'L1' }
vi.mock('../api/tasks', async (orig) => ({
  ...(await orig<typeof import('../api/tasks')>()),
  getTasks: vi.fn(async () => [
    { id: 't1', title: 'Посчитать p95', text: 'Дан лог запросов', specialization: 'backend', deadline: '2026-10-16T12:00:00Z', has_reference: true, answer_max: 5000, company, my_submission: null },
    { id: 't2', title: 'Оптимизировать запрос', text: 'Медленный JOIN', specialization: 'backend', deadline: '2026-10-17T12:00:00Z', has_reference: true, company, my_submission: { status: 'auto_correct', comment: null } },
    { id: 't3', title: 'Спроектировать API', text: 'Описать ресурсы', specialization: 'backend', deadline: '2026-10-18T12:00:00Z', has_reference: false, company, my_submission: { status: 'rejected', comment: 'Не хватает ошибок' } },
  ]),
  submitTask: (id: string, answer: string) => h.submit(id, answer),
  complainTask: (id: string, comment: string) => h.complain(id, comment),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><TasksPage /></MemoryRouter></QueryClientProvider>)

describe('TasksPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the company trust level, states autocheck and sends an answer', async () => {
    setup()
    expect(await screen.findByText('Посчитать p95')).toBeInTheDocument()
    expect(screen.getAllByText(/Корп · уровень L1/)).toHaveLength(3)
    expect(screen.getAllByText(/проверим автоматически/)).toHaveLength(2)
    const send = screen.getByRole('button', { name: 'Отправить' })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Ответ на задачу «Посчитать p95»'), 'ответ')
    await userEvent.click(send)
    expect(h.submit).toHaveBeenCalledWith('t1', 'ответ')
  })

  it('limits the answer by the server value and explains a rejected submission', async () => {
    h.submit.mockRejectedValueOnce(new ApiError(422, 'validation', 'Ошибка проверки', 'Срок задачи истёк'))
    setup()
    const box = await screen.findByLabelText('Ответ на задачу «Посчитать p95»')
    expect(box).toHaveAttribute('maxlength', '5000')
    await userEvent.type(box, 'ответ')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ошибка проверки: Срок задачи истёк')
  })

  it('shows the status of the own submission with the comment and no form', async () => {
    setup()
    expect(await screen.findByText(/совпадает с эталоном/)).toBeInTheDocument()
    expect(screen.getByText(/не принято/)).toBeInTheDocument()
    expect(screen.getByText(/Не хватает ошибок/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Отправить' })).toHaveLength(1)
  })

  it('complains about free work with a comment', async () => {
    setup()
    await userEvent.click((await screen.findAllByRole('button', { name: 'Пожаловаться: бесплатная работа' }))[0])
    await userEvent.type(screen.getByLabelText('Комментарий к жалобе'), 'Реальная задача из бэклога')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить жалобу' }))
    expect(h.complain).toHaveBeenCalledWith('t1', 'Реальная задача из бэклога')
    expect(await screen.findByText(/жалоба отправлена/i)).toBeInTheDocument()
  })
})
