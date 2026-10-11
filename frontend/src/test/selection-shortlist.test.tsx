import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { unpin, type Card } from '../api/employer'
import SelectionPage from '../pages/employer/SelectionPage'

const card: Card = {
  ref: 'r1', alias: 'B-M-ABCD', grade: 'middle', grade_status: 'confirmed', block: 1, fit_level: null, readiness: null,
  stack: [], skills: [], experience_years: 4, formats: ['remote'], city: null, conflicts: [], pinned: true, express: false,
  filter_mismatch: null, explanation: { lines: [], missing: [], counterfactual: null }, contact_status: null,
}
vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getNeed: vi.fn(async () => ({ id: 'n1', title: 'Бэкенд', specialization: 'backend', grades: ['middle'], must: ['Go'], nice: [], formats: ['remote'], city: null, salary_from: 1, salary_to: 2, gross_net: 'gross', contact_method: 'chat', status: 'active' })),
  getSelection: vi.fn(async () => ({ blocks: [], shortlist: [card], diff: null, suggestions: [], fork_fit: { fit: 18, total: 24 } })),
  unpin: vi.fn(async () => undefined),
}))
vi.mock('../api/contacts', async (orig) => ({ ...(await orig<typeof import('../api/contacts')>()), getQuota: vi.fn(async () => ({ used: 3, limit: 10 })) }))

describe('Подборка: шортлист и сводки', () => {
  it('lists shortlisted candidates compactly and unpins them', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/employer/needs/n1']}>
      <Routes><Route path="/employer/needs/:id" element={<SelectionPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    const aside = await screen.findByRole('complementary', { name: 'Шортлист' })
    expect(await within(aside).findByText('B-M-ABCD')).toBeInTheDocument()
    expect(within(aside).getByText(/Middle · подтверждён тестом/)).toBeInTheDocument()
    expect(screen.getByText('у 18 из 24')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /квота 3 из 10/ })).toHaveAttribute('href', '/employer/needs/n1/invitations')
    await userEvent.click(within(aside).getByRole('button', { name: 'Убрать B-M-ABCD из шортлиста' }))
    expect(unpin).toHaveBeenCalledWith('n1', 'r1')
  })
})
