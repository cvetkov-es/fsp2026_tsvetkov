import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import DemandBlock from '../components/candidate/DemandBlock'

const h = vi.hoisted(() => ({ data: null as unknown }))
vi.mock('../api/initiative', () => ({ getDemand: vi.fn(async () => h.data) }))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><DemandBlock /></MemoryRouter></QueryClientProvider>)

describe('DemandBlock', () => {
  it('without enough companies shows no numbers', async () => {
    h.data = { category: 'Backend · Middle', enough: false, companies: null, min_companies: 5, window_days: 30, top: [], skills: [] }
    setup()
    expect(await screen.findByText(/Покажем спрос, когда «Backend · Middle» будут искать хотя бы 5 компаний/)).toBeInTheDocument()
    expect(screen.getByText(/Backend · Middle/)).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('with enough companies lists the techs and calls to confirm a skill', async () => {
    h.data = {
      category: 'Backend · Middle', enough: true, companies: 7, min_companies: 5, window_days: 30,
      top: [{ tech: 'Docker', share: 1, state: 'missing', skill: 'devops' }, { tech: 'Python', share: 0.6, state: 'confirmed', skill: null }],
      skills: [{ code: 'devops', title: 'DevOps и контейнеры', share: 1 }],
    }
    setup()
    expect(await screen.findByText(/За 30 дней 7 компаний искали/)).toBeInTheDocument()
    expect(screen.getByText('Docker: 100% (не подтверждено)')).toBeInTheDocument()
    expect(screen.getByText('Python: 60% (подтверждено)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Подтвердите навык «DevOps и контейнеры»' })).toHaveAttribute('href', '/candidate/skills')
  })
})
