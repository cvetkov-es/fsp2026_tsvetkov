import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CompaniesPage from '../pages/candidate/CompaniesPage'

const h = vi.hoisted(() => ({
  data: null as unknown,
  send: vi.fn(async (_id: string) => ({ signal_id: 'sig-new', signals_left: 1 })),
  withdraw: vi.fn(async (_id: string) => ({ signal_id: 'sig1', signals_left: 1 })),
}))
vi.mock('../api/initiative', () => ({
  getCompanies: vi.fn(async () => h.data),
  sendSignal: (id: string) => h.send(id),
  withdrawSignal: (id: string) => h.withdraw(id),
}))

const items = [
  { id: 'c1', name: 'Первая', industry: 'финтех', description: null, trust_level: 'L0', open_needs: 2, signal_id: null },
  { id: 'c2', name: 'Вторая', industry: null, description: 'Платежи', trust_level: 'L2', open_needs: 1, signal_id: 'sig1' },
]
const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><CompaniesPage /></MemoryRouter></QueryClientProvider>)

describe('CompaniesPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the quarter limit, marks unverified companies and sends and withdraws a signal', async () => {
    h.data = { signals_left: 2, signals_limit: 3, items }
    setup()
    expect(await screen.findByText('Осталось отметок в этом квартале: 2 из 3')).toBeInTheDocument()
    expect(screen.getByText('не проверена')).toBeInTheDocument()
    expect(screen.getByText(/Компания увидит отметку, если вы прошли тест и профиль открыт для предложений/)).toBeInTheDocument()
    expect(screen.getByText('открытых потребностей: 2')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Хочу к вам' }))
    expect(h.send).toHaveBeenCalledWith('c1')
    await userEvent.click(screen.getByRole('button', { name: /Интерес отмечен · отменить/ }))
    expect(h.withdraw).toHaveBeenCalledWith('sig1')
  })

  it('disables sending when no signals are left', async () => {
    h.data = { signals_left: 0, signals_limit: 3, items }
    setup()
    expect(await screen.findByRole('button', { name: 'Хочу к вам' })).toBeDisabled()
    expect(screen.getByText(/Отметки на этот квартал закончились/)).toBeInTheDocument()
  })
})
