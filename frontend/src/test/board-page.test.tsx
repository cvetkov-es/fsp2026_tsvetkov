import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Board, BoardCard, StageInput } from '../api/hiring'
import BoardPage from '../pages/employer/BoardPage'

const areas = [{ code: 'db', title: 'БД и SQL' }, { code: 'http', title: 'HTTP и API' }]
const card = (over: Partial<BoardCard>): BoardCard => ({
  contact_id: 'c1', alias: 'B-M-AAAA', grade: 'middle', revoked: false, stage: null, stage_at: '2026-10-08T10:00:00Z', level: null, reason: null,
  weak_areas: [], vote: null, vote_note: null, chat_open: true, area_options: areas, ...over,
})
const board: Board = {
  need_id: 'n1', title: 'Бэкенд', trust_level: 'L2', vote_weight: 1, votes_used: 1, votes_limit: 30, dispute_days: 7,
  cards: [card({}), card({ contact_id: 'c2', alias: 'B-M-BBBB', stage: 'technical', level: 'meets', vote: { value: 'meets', state: 'pending', effective_at: '2026-10-15T10:00:00Z' } }),
    card({ contact_id: 'c3', alias: 'B-M-CCCC', stage: 'first', vote_note: 'duplicate' }),
    card({ contact_id: 'c4', alias: 'B-M-DDDD', stage: 'offer', revoked: true, chat_open: false })],
}
const api = vi.hoisted(() => ({ getBoard: vi.fn<() => Promise<Board>>(), moveStage: vi.fn<(id: string, body: StageInput) => Promise<BoardCard>>() }))
vi.mock('../api/hiring', async (orig) => ({ ...(await orig<typeof import('../api/hiring')>()), ...api }))

const show = () => render(
  <QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/employer/needs/n1/board']}>
    <Routes><Route path="/employer/needs/:id/board" element={<BoardPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>)

beforeEach(() => { vi.clearAllMocks(); api.getBoard.mockResolvedValue(board); api.moveStage.mockResolvedValue(card({})) })

describe('BoardPage', () => {
  it('shows stage columns, vote states and why an answer did not become a vote', async () => {
    show()
    const technical = await screen.findByRole('region', { name: 'Техническое интервью' })
    expect(within(technical).getByText('B-M-BBBB')).toBeInTheDocument()
    expect(within(technical).getByText(/Оценка: вступит в силу 15\.10\.2026/)).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Первичное интервью' })).getByText(/Оценка не засчитана: оценка вашей компании по этому кандидату уже есть/)).toBeInTheDocument()
    expect(screen.getByText(/вступит в силу через 7 дней.*Оценок за 30 дней: 1 из 30/)).toBeInTheDocument()
    const offer = within(screen.getByRole('region', { name: 'Оффер' }))
    expect(offer.getByText('Кандидат скрыл контакты. Карточка доступна только для просмотра.')).toBeInTheDocument()
    expect(offer.queryByRole('button', { name: 'Изменить этап' })).not.toBeInTheDocument()
  })

  it('asks about the level on the technical stage and saves it', async () => {
    show()
    const fresh = within(await screen.findByRole('region', { name: 'Приглашение принято' }))
    const toggle = fresh.getByRole('button', { name: 'Изменить этап' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(fresh.getByRole('button', { name: 'Скрыть' })).toHaveAttribute('aria-expanded', 'true')
    await userEvent.selectOptions(fresh.getByLabelText('Этап'), 'technical')
    expect(fresh.getByText('Уровень относительно ваших ожиданий от грейда Middle')).toBeInTheDocument()
    const save = fresh.getByRole('button', { name: 'Сохранить' })
    expect(save).toBeDisabled()
    await userEvent.click(fresh.getByLabelText('выше ожиданий'))
    await userEvent.click(save)
    expect(api.moveStage).toHaveBeenCalledWith('c1', { stage: 'technical', level: 'above', reason: undefined, weak_areas: [] })
  })

  it('a rejection needs a reason and may name weak areas', async () => {
    show()
    const fresh = within(await screen.findByRole('region', { name: 'Приглашение принято' }))
    await userEvent.click(fresh.getByRole('button', { name: 'Изменить этап' }))
    await userEvent.selectOptions(fresh.getByLabelText('Этап'), 'rejected')
    await userEvent.click(fresh.getByLabelText('ниже ожиданий'))
    expect(fresh.getByRole('button', { name: 'Сохранить' })).toBeDisabled()
    await userEvent.selectOptions(fresh.getByLabelText('Причина отказа'), 'level_below')
    await userEvent.click(fresh.getByLabelText('БД и SQL'))
    await userEvent.click(fresh.getByRole('button', { name: 'Сохранить' }))
    expect(api.moveStage).toHaveBeenCalledWith('c1', { stage: 'rejected', level: 'below', reason: 'level_below', weak_areas: ['db'] })
  })

  it('without a known grade the level question does not name one', async () => {
    api.getBoard.mockResolvedValue({ ...board, cards: [card({ grade: null })] })
    show()
    const fresh = within(await screen.findByRole('region', { name: 'Приглашение принято' }))
    await userEvent.click(fresh.getByRole('button', { name: 'Изменить этап' }))
    await userEvent.selectOptions(fresh.getByLabelText('Этап'), 'technical')
    expect(fresh.getByText('Уровень относительно ваших ожиданий')).toBeInTheDocument()
  })

  it('takes the dispute window from the server and shows load errors', async () => {
    api.getBoard.mockResolvedValueOnce({ ...board, dispute_days: 3 })
    const { unmount } = show()
    expect(await screen.findByText(/вступит в силу через 3 дня/)).toBeInTheDocument()
    unmount()
    api.getBoard.mockRejectedValueOnce(new Error('boom'))
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/employer/needs/n1/board']}>
        <Routes><Route path="/employer/needs/:id/board" element={<BoardPage />} /></Routes>
      </MemoryRouter></QueryClientProvider>)
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить доску')
  })
})
