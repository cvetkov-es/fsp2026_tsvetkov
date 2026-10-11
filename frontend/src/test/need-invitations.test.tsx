import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import NeedInvitationsPage from '../pages/employer/NeedInvitationsPage'

vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getNeedInvitations: vi.fn(async () => [{ id: 'k1', status: 'offer_v2', version: 2, ref: 'abcd1234', alias: 'B-M-ABCD', salary_from: 250000,
    salary_to: 320000, gross_net: 'gross', expires_at: '2026-10-20T00:00:00Z', counter_amount: 320000, counter_comment: null,
    counter_expires_at: null, decline_reason: null, created_at: '2026-10-08T00:00:00Z', chat_open: false, viewed: true, hours_per_week: 20 }]),
  getQuota: vi.fn(async () => ({ used: 1, limit: 3 })),
}))
vi.mock('../api/employer', async (orig) => ({ ...(await orig<typeof import('../api/employer')>()), getNeed: vi.fn(async () => ({ title: 'Бэкенд' })) }))

describe('NeedInvitationsPage', () => {
  it('shows that the candidate opened offer v2', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/employer/needs/n1/invitations']}>
      <Routes><Route path="/employer/needs/:id/invitations" element={<NeedInvitationsPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('обновлённое приглашение · версия 2 · просмотрено')).toBeInTheDocument()
    expect(screen.getByText(/20 ч в неделю/)).toBeInTheDocument()  // кандидату нет 18: компания видит оговорённые часы
  })
})
