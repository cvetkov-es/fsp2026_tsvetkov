import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { blockCompany, declineInvitation, getBlocks, unblockCompany, type Invitation } from '../api/contacts'
import InvitationsPage from '../pages/candidate/InvitationsPage'

const base: Invitation = {
  id: 'i1', status: 'viewed', version: 1, company: { id: 'c1', name: 'Корп', industry: 'финтех', description: null, trust_level: 'L2' },
  need_title: 'Бэкенд', salary_from: 250000, salary_to: 350000, gross_net: 'gross', salary_to_net: 304500, description: '', why_you: 'Middle подтверждён тестом',
  next_step: 'Созвон', contact_method: 'chat', expires_at: '2026-10-20T00:00:00Z', counter_amount: null, counter_expires_at: null, created_at: '2026-10-08T00:00:00Z', chat_open: false,
}
const accept = vi.fn<(id: string) => Promise<Invitation>>(async () => ({ ...base, status: 'accepted', chat_open: true }))
vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getMyInvitations: vi.fn(async () => [base, { ...base, id: 'i2', company: { ...base.company, id: 'c2', name: 'Другая' }, salary_to: 300000, salary_to_net: 300000, gross_net: 'net' }]),
  viewInvitation: vi.fn(async () => base),
  acceptInvitation: (id: string) => accept(id),
  declineInvitation: vi.fn(async () => base), blockCompany: vi.fn(async () => undefined),
  getBlocks: vi.fn(async () => []), unblockCompany: vi.fn(async () => undefined),
}))
vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: vi.fn(async () => ({ texts: [{ type: 'contact_transfer', title: 'Согласие на передачу контактов компании', body: 'Текст' }] })),
}))

describe('InvitationsPage', () => {
  it('compares offers side by side and accepts only with consent №4', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><InvitationsPage /></MemoryRouter></QueryClientProvider>)
    const boxes = await screen.findAllByLabelText('сравнить')
    await userEvent.click(boxes[0])
    await userEvent.click(boxes[1])
    expect(screen.getByText('Сравнение приглашений')).toBeInTheDocument()
    expect(screen.getByText('304 500 ₽')).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'Открыть' })[0])
    const acceptBtn = await screen.findByRole('button', { name: /принять приглашение/i })
    expect(acceptBtn).toBeDisabled()
    await userEvent.click(await screen.findByLabelText(/Согласие на передачу контактов компании/))
    await userEvent.click(acceptBtn)
    expect(accept).toHaveBeenCalledWith('i1')
  })

  it('declines with a comment and hides a company only after confirmation', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><InvitationsPage /></MemoryRouter></QueryClientProvider>)
    await userEvent.click((await screen.findAllByRole('button', { name: 'Открыть' }))[0])
    await userEvent.type(await screen.findByLabelText('Комментарий к отказу'), 'Ищу удалёнку')
    await userEvent.click(screen.getByRole('button', { name: 'Отклонить' }))
    expect(declineInvitation).toHaveBeenCalledWith('i1', 'salary', 'Ищу удалёнку')
    await userEvent.click(screen.getByRole('button', { name: 'Не показывать эту компанию' }))
    expect(blockCompany).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /да, скрыть/i }))
    expect(blockCompany).toHaveBeenCalledWith('c1')
  })

  it('lists hidden companies and lets them back', async () => {
    vi.mocked(getBlocks).mockResolvedValue([{ id: 'c9', name: 'Скрытая', industry: null, description: null, trust_level: 'L0' }])
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><InvitationsPage /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('Скрытая')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'вернуть' }))
    expect(unblockCompany).toHaveBeenCalledWith('c9')
  })
})
