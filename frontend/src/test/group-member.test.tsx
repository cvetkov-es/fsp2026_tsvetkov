import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Invitation } from '../api/contacts'
import InvitationsPage from '../pages/candidate/InvitationsPage'

const h = vi.hoisted(() => ({
  list: [] as unknown[],
  accept: vi.fn(async (_id: string) => ({})),
  withdraw: vi.fn(async (_id: string) => ({})),
  decline: vi.fn(async () => ({})),
}))
const base: Invitation = {
  id: 'i1', status: 'viewed', version: 1, company: { id: 'k1', name: 'Корп', industry: null, description: null, trust_level: 'L2' }, need_title: 'Бэкенд',
  salary_from: 250000, salary_to: 350000, gross_net: 'gross', salary_to_net: 304500, description: '', why_you: 'Сыгранная команда', next_step: 'Созвон',
  contact_method: 'chat', expires_at: '2026-10-12T00:00:00Z', counter_amount: null, counter_expires_at: null, created_at: '2026-10-09T00:00:00Z', chat_open: false,
}
const group = { team_name: 'Byte Force', size: 3, min_size: 2, deadline: '2026-10-12T00:00:00Z', state: 'open', min_reached_now: null as boolean | null }
vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getMyInvitations: vi.fn(async () => h.list),
  viewInvitation: vi.fn(async () => base),
  declineInvitation: (...a: unknown[]) => h.decline(...(a as [])),
  getBlocks: vi.fn(async () => []),
}))
vi.mock('../api/groups', async (orig) => ({
  ...(await orig<typeof import('../api/groups')>()),
  conditionalAccept: (id: string) => h.accept(id),
  conditionalWithdraw: (id: string) => h.withdraw(id),
}))
vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: vi.fn(async () => ({ texts: [{ type: 'contact_transfer', title: 'Согласие на передачу контактов компании', body: 'Текст' }] })),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><InvitationsPage /></MemoryRouter></QueryClientProvider>)

describe('team invitation on the candidate side', () => {
  beforeEach(() => vi.clearAllMocks())

  it('offers a conditional answer, no consent №4 and no counter offer before the offer v2', async () => {
    h.list = [{ ...base, group: { ...group } }]
    setup()
    expect(await screen.findByText(/Командное приглашение: команда «Byte Force», 3 участника, минимум 2, ответ до 12\.10/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Открыть' }))
    expect(screen.queryByRole('button', { name: /принять приглашение/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Согласие на передачу контактов компании/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Предложить сумму/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Согласиться условно' }))
    expect(h.accept).toHaveBeenCalledWith('i1')
    expect(screen.getByRole('button', { name: 'Отклонить' })).toBeInTheDocument()
  })

  it('says nothing about the minimum when the server did not send it', async () => {
    h.list = [{ ...base, group: { ...group, min_reached_now: null } }]
    setup()
    await screen.findByText(/Командное приглашение/)
    expect(screen.queryByText(/минимальный состав/i)).not.toBeInTheDocument()
  })

  it('shows the minimum status when the server sent it', async () => {
    h.list = [{ ...base, group: { ...group, min_reached_now: true } }]
    setup()
    expect(await screen.findByText(/минимальный состав набран/i)).toBeInTheDocument()
  })

  it('after a conditional answer the candidate may withdraw it until the deadline', async () => {
    h.list = [{ ...base, status: 'conditionally_accepted', group: { ...group } }]
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Отозвать согласие' }))
    expect(h.withdraw).toHaveBeenCalledWith('i1')
  })

  it('no withdraw button once the group deadline has passed', async () => {
    h.list = [{ ...base, status: 'conditionally_accepted', group: { ...group, state: 'min_reached' } }]
    setup()
    await screen.findByText(/Командное приглашение/)
    expect(screen.queryByRole('button', { name: 'Отозвать согласие' })).not.toBeInTheDocument()
  })

  it('after the deadline without the minimum the candidate may still withdraw or decline, and the text says no offer is coming', async () => {
    h.list = [{ ...base, status: 'conditionally_accepted', group: { ...group, state: 'not_reached' } }]
    setup()
    expect(await screen.findByText(/Личного приглашения не будет/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отозвать согласие' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отказаться' })).toBeInTheDocument()
  })

  it('after the offer v2 it is a regular offer with consent №4', async () => {
    h.list = [{ ...base, status: 'offer_v2', version: 2, group: { ...group, state: 'closed' } }]
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Открыть' }))
    expect(await screen.findByRole('button', { name: /принять приглашение/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Согласиться условно/ })).not.toBeInTheDocument()
  })
})
