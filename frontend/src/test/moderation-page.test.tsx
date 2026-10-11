import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { ModerationCase } from '../api/moderation'
import ModerationPage from '../pages/ModerationPage'

const base = { status: 'open' as const, created_at: '2026-10-09T10:00:00Z', due_at: null, resolution: null, resolution_text: null }
const dispute: ModerationCase = {
  ...base, id: 'k1', type: 'vote_dispute', type_title: 'Спор об оценке', comment: 'Созвона не было',
  summary: [
    { label: 'Компания', value: 'Корп' }, { label: 'Кандидат', value: 'B-M-AAAA' },
    { label: 'Оценка', value: '«ниже ожиданий» (грейд Middle, 08.10.2026)' }, { label: 'Причина спора', value: 'собеседования не было' },
    { label: 'Этапы', value: 'Техническое интервью 08.10.2026' },
  ],
  actions: [{ code: 'annul', title: 'Аннулировать оценку' }, { code: 'uphold', title: 'Оставить в силе' }],
}
const freeWork: ModerationCase = {
  ...base, id: 'k2', type: 'free_work', type_title: '«Бесплатная работа»', comment: 'Это задача из бэклога',
  summary: [{ label: 'Компания', value: 'Корп' }, { label: 'Задача', value: 'Посчитать p95' }, { label: 'Решений', value: '3' }],
  actions: [{ code: 'remove', title: 'Снять задачу' }, { code: 'dismiss', title: 'Отклонить жалобу' }],
}
const art16: ModerationCase = {
  ...base, id: 'k3', type: 'art16', type_title: 'Возражение по ст. 16', comment: 'Прошу пересмотреть', due_at: '2026-11-08T10:00:00Z',
  summary: [{ label: 'Решение', value: 'грейд не подтверждён' }],
  actions: [{ code: 'recheck', title: 'Назначить повторную проверку' }, { code: 'explain', title: 'Подтвердить решение' }],
}
const api = vi.hoisted(() => ({ getCases: vi.fn(async (): Promise<ModerationCase[]> => [dispute]), resolveCase: vi.fn(async () => ({ ...dispute, status: 'resolved' })) }))
vi.mock('../api/moderation', async (orig) => ({ ...(await orig<typeof import('../api/moderation')>()), ...api }))

const show = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ModerationPage /></MemoryRouter></QueryClientProvider>)

describe('ModerationPage', () => {
  it('draws any case from its summary rows and buttons, and resolves with the chosen action', async () => {
    show()
    expect(await screen.findByText('Спор об оценке')).toBeInTheDocument()
    expect(screen.getByText('Корп')).toBeInTheDocument()
    expect(screen.getByText('«ниже ожиданий» (грейд Middle, 08.10.2026)')).toBeInTheDocument()
    expect(screen.getByText('Техническое интервью 08.10.2026')).toBeInTheDocument()
    expect(screen.getByText(/Созвона не было/)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Комментарий к решению'), 'Компания подтвердила ошибку')
    await userEvent.click(screen.getByRole('button', { name: 'Аннулировать оценку' }))
    expect(api.resolveCase).toHaveBeenCalledWith('k1', 'annul', 'Компания подтвердила ошибку')
  })

  it('the first action is the main button, the rest are secondary', async () => {
    api.getCases.mockResolvedValueOnce([freeWork])
    show()
    const dismiss = await screen.findByRole('button', { name: 'Отклонить жалобу' })
    expect(screen.queryByRole('button', { name: 'Аннулировать оценку' })).not.toBeInTheDocument()  // кнопки — только своего типа
    await userEvent.click(dismiss)
    expect(api.resolveCase).toHaveBeenCalledWith('k2', 'dismiss', '')
  })

  it('shows the answer deadline of a case that has one', async () => {
    api.getCases.mockResolvedValueOnce([art16])
    show()
    expect(await screen.findByText('Ответить до 08.11.2026')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Назначить повторную проверку' })).toBeEnabled()
  })

  it('says so when the queue is empty', async () => {
    api.getCases.mockResolvedValueOnce([])
    show()
    expect(await screen.findByText('Открытых обращений нет.')).toBeInTheDocument()
  })
})
