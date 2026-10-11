import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { Board, BoardCard } from '../api/hiring'
import BoardPage from '../pages/employer/BoardPage'

const card: BoardCard = {
  contact_id: 'c1', alias: 'B-M-AAAA', grade: 'middle', revoked: false, stage: 'technical', stage_at: '2026-10-08T10:00:00Z', level: null,
  reason: null, weak_areas: [], vote: null, vote_note: null, chat_open: true, area_options: [],
}
const h = vi.hoisted(() => ({
  trust: 'L2',
  helper: vi.fn(async (_id: string) => ({
    questions: [
      { text: 'Как бы вы нашли причину внезапно медленного запроса в PostgreSQL на проде?', topic: 'БД и SQL', reason: 'слабая область по итогам этапа' },
      { text: 'Как вы проверяете код, который предложил ИИ-ассистент, прежде чем принять его?', topic: 'Работа с ИИ', reason: 'навык подтверждён тестом, спросите глубже' },
    ],
    used: 3, limit: 30, window_days: 14,
  })),
}))
vi.mock('../api/hiring', async (orig) => ({
  ...(await orig<typeof import('../api/hiring')>()),
  getBoard: vi.fn(async (): Promise<Board> => ({ need_id: 'n1', title: 'Бэкенд', trust_level: h.trust, vote_weight: 1, votes_used: 0, votes_limit: 30, dispute_days: 7, cards: [card, { ...card, contact_id: 'c2', alias: 'B-M-BBBB', chat_open: false, revoked: true }] })),
  getInterviewHelper: (id: string) => h.helper(id),
}))

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={['/employer/needs/n1/board']}><Routes><Route path="/employer/needs/:id/board" element={<BoardPage />} /></Routes></MemoryRouter></QueryClientProvider>)

describe('interview helper on the hiring board', () => {
  beforeEach(() => { vi.clearAllMocks(); h.trust = 'L2' })

  it('shows the questions with topic and reason and how many sets are used', async () => {
    show()
    const technical = within(await screen.findByRole('region', { name: 'Техническое интервью' }))
    await userEvent.click(technical.getByRole('button', { name: 'Вопросы к собеседованию' }))
    expect(h.helper).toHaveBeenCalledWith('c1')
    expect(await screen.findByText(/Как бы вы нашли причину внезапно медленного запроса/)).toBeInTheDocument()
    expect(screen.getByText(/БД и SQL · слабая область по итогам этапа/)).toBeInTheDocument()
    expect(screen.getByText(/Работа с ИИ · навык подтверждён тестом, спросите глубже/)).toBeInTheDocument()
    expect(screen.getByText('Использовано 3 из 30 за 14 дней')).toBeInTheDocument()  // окно лимита — число с сервера
  })

  it('is offered only for L2 and above and only while the contacts are open', async () => {
    h.trust = 'L1'
    show()
    await screen.findByRole('region', { name: 'Техническое интервью' })
    expect(screen.queryByRole('button', { name: 'Вопросы к собеседованию' })).not.toBeInTheDocument()
  })

  it('a card with hidden contacts has no helper button', async () => {
    show()
    await screen.findByText('B-M-BBBB')
    expect(screen.getAllByRole('button', { name: 'Вопросы к собеседованию' })).toHaveLength(1)
  })

  it('explains the limit error in plain words', async () => {
    h.helper.mockRejectedValueOnce(new ApiError(409, 'helper_limit', 'Лимит вопросов к собеседованию на этот месяц исчерпан', 'Использовано 30 из 30 за 30 дней'))
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Вопросы к собеседованию' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Лимит вопросов к собеседованию на этот месяц исчерпан: Использовано 30 из 30 за 30 дней')
  })
})
