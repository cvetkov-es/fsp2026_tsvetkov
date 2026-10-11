import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { closeNeed, getSelection } from '../api/employer'
import SelectionPage from '../pages/employer/SelectionPage'

vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getNeed: vi.fn(async () => ({ id: 'n1', title: 'Бэкенд', specialization: 'backend', grades: ['middle'], must: ['Python'], nice: [], formats: ['remote'], city: null, salary_from: 1, salary_to: 2, gross_net: 'gross', contact_method: 'chat', status: 'active' })),
  getSelection: vi.fn(async () => ({ blocks: [{ block: 1, title: 'Подтверждённые: Middle', items: [] }, { block: 4, title: 'Почти подходят', items: [] }], shortlist: [],
    diff: { added: 3, removed: [{ ref: 'r', alias: 'B-M-0001', reason: 'не проходит: нет Kafka' }, { ref: 'q', alias: 'B-M-0002', reason: 'не проходит: нет Kafka' }] },
    suggestions: [{ filter: 'techs', label: 'снять «технологии»', gain: 5 }] })),
  closeNeed: vi.fn(async () => ({})),
}))

const page = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/employer/needs/n1']}>
  <Routes><Route path="/employer/needs/:id" element={<SelectionPage />} /><Route path="/" element={<p>Главная</p>} /></Routes></MemoryRouter></QueryClientProvider>)

describe('SelectionPage', () => {
  it('renders block headers, diff grouped by reason and suggestions', async () => {
    page()
    expect(await screen.findByText('Подтверждённые: Middle')).toBeInTheDocument()
    expect(screen.getByText('Почти подходят')).toBeInTheDocument()
    expect(screen.getByText(/\+3 новых, −2 выбыли/)).toBeInTheDocument()
    expect(screen.getByText(/не проходит: нет Kafka, 2 чел\./)).toBeInTheDocument()
    expect(screen.getByText(/снять «технологии»: \+5/)).toBeInTheDocument()
  })

  it('filters by confirmed skills', async () => {
    page()
    await userEvent.click(await screen.findByRole('button', { name: 'Работа с ИИ' }))
    await waitFor(() => expect(getSelection).toHaveBeenLastCalledWith('n1', { skills: ['ai'] }))
  })

  it('closes the need and returns home', async () => {
    page()
    await userEvent.click(await screen.findByRole('button', { name: /закрыть потребность/i }))
    expect(closeNeed).toHaveBeenCalledWith('n1')
    expect(await screen.findByText('Главная')).toBeInTheDocument()
  })

  it('says so when nobody matches even without filters', async () => {
    vi.mocked(getSelection).mockResolvedValueOnce({ blocks: [], shortlist: [], diff: null, suggestions: [] })
    page()
    expect(await screen.findByText(/под условия потребности пока никого нет/i)).toBeInTheDocument()
  })
})
