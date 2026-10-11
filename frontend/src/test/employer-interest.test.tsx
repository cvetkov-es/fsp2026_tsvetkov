import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Card } from '../api/employer'
import { CandidateCard } from '../components/employer/CandidateCard'
import EmployerHome from '../pages/employer/EmployerHome'

const h = vi.hoisted(() => ({ interest: [] as object[] }))
vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getCompany: vi.fn(async () => ({ id: 'k1', name: 'Корп', description: null, industry: null, contacts: {}, trust_level: 'L2' })),
  listNeeds: vi.fn(async () => []),
}))
vi.mock('../api/initiative', async (orig) => ({
  ...(await orig<typeof import('../api/initiative')>()),
  getInterest: vi.fn(async () => h.interest),
}))

const qc = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
const home = () => render(<QueryClientProvider client={qc()}><MemoryRouter><EmployerHome /></MemoryRouter></QueryClientProvider>)

const card: Card = {
  ref: 'aaaa1111', alias: 'B-M-AAAA', grade: 'middle', grade_status: 'confirmed', block: 1, fit_level: 'high', readiness: null,
  stack: [], skills: [], experience_years: null, formats: [], city: null, conflicts: [], pinned: false, express: false,
  filter_mismatch: null, explanation: { lines: ['Middle подтверждён тестом'], missing: [], counterfactual: null },
}

describe('company interest', () => {
  it('lists the candidates who signaled, without personal data', async () => {
    h.interest = [{ ref: 'aaaa1111', alias: 'B-M-AAAA', specialization: 'backend', grade: 'middle', grade_status: 'confirmed', at: '2026-10-09T10:00:00Z' }]
    home()
    expect(await screen.findByText('Интерес к компании')).toBeInTheDocument()
    expect(await screen.findByText(/B-M-AAAA/)).toBeInTheDocument()
    expect(screen.getByText(/стоят выше в ваших подборках/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Задачи' })).toHaveAttribute('href', '/employer/tasks')
    expect(screen.getByRole('link', { name: 'Вакансии' })).toHaveAttribute('href', '/employer/vacancies')
  })

  it('says so when nobody has signaled yet', async () => {
    h.interest = []
    home()
    expect(await screen.findByText('Пока никто не отметил интерес')).toBeInTheDocument()
  })

  it('card shows the «wants to join you» chip only with a signal', () => {
    const { rerender } = render(<CandidateCard card={{ ...card, signal: true }} />)
    expect(screen.getByText('Хочет к вам')).toBeInTheDocument()
    rerender(<CandidateCard card={card} />)
    expect(screen.queryByText('Хочет к вам')).not.toBeInTheDocument()
  })
})
