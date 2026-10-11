import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GroupPage from '../pages/employer/GroupPage'

const h = vi.hoisted(() => ({
  group: null as unknown,
  finalize: vi.fn(async (_id: string) => ({})),
  withdraw: vi.fn(async (_id: string) => ({})),
}))
vi.mock('../api/groups', async (orig) => ({
  ...(await orig<typeof import('../api/groups')>()),
  getGroup: vi.fn(async () => h.group),
  finalizeGroup: (id: string) => h.finalize(id),
  withdrawGroup: (id: string) => h.withdraw(id),
}))

const members = [
  { contact_id: 'c1', alias: 'B-M-AAAA', status: 'conditionally_accepted', salary_from: 200000, salary_to: 300000, hours_per_week: null },
  { contact_id: 'c2', alias: 'B-M-BBBB', status: 'conditionally_accepted', salary_from: 200000, salary_to: 280000, hours_per_week: null },
  { contact_id: 'c3', alias: 'B-J-CCCC', status: 'expired', salary_from: 100000, salary_to: 120000, hours_per_week: 20 },
]
const group = (over: object) => ({ id: 'g1', team_name: 'Byte Force', need_id: 'n1', need_title: 'Бэкенд', min_size: 2, size: 3, deadline: '2026-10-12T10:00:00Z',
  state: 'open', min_reached_now: true, members, ...over })
const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={['/employer/groups/g1']}><Routes><Route path="/employer/groups/:id" element={<GroupPage />} /></Routes></MemoryRouter></QueryClientProvider>)

describe('GroupPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the team, the status of every member and that the minimum is reached while open', async () => {
    h.group = group({})
    setup()
    expect(await screen.findByRole('heading', { name: 'Команда «Byte Force» · потребность «Бэкенд»' })).toBeInTheDocument()
    expect(screen.getByText('открыто до 12.10 · минимум набран')).toBeInTheDocument()
    expect(screen.getAllByText('условное согласие')).toHaveLength(2)
    expect(screen.getByText('истекло')).toBeInTheDocument()
    expect(screen.getByText(/20 ч в неделю/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отправить личные приглашения согласившимся' })).not.toBeInTheDocument()  // срок ещё не вышел
  })

  it('after the deadline with the minimum reached offers v2 and the group can be withdrawn', async () => {
    h.group = group({ state: 'min_reached' })
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Отправить личные приглашения согласившимся' }))
    expect(h.finalize).toHaveBeenCalledWith('g1')
    await userEvent.click(screen.getByRole('button', { name: 'Отозвать приглашение команды' }))
    expect(h.withdraw).toHaveBeenCalledWith('g1')
  })

  it('says the minimum is not reached and offers no v2', async () => {
    h.group = group({ state: 'not_reached', min_reached_now: false })
    setup()
    expect(await screen.findByText('минимум не набран')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отправить личные приглашения согласившимся' })).not.toBeInTheDocument()
  })

  it('a closed group has no actions', async () => {
    h.group = group({ state: 'closed' })
    setup()
    expect(await screen.findByText('закрыто')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отозвать приглашение команды' })).not.toBeInTheDocument()
  })
})
