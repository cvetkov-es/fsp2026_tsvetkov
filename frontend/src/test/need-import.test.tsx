import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import NeedForm from '../pages/employer/NeedForm'

vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  getStackDict: vi.fn(async () => []),
  parseNeed: vi.fn(async () => ({ source: 'rules', title: 'Python-разработчик', specialization: 'backend', grades: ['middle'], must: ['Python', 'PostgreSQL'],
    nice: ['Kafka'], formats: ['remote'], city: null, salary_from: 250000, salary_to: null, gross_net: 'gross', unknown_terms: ['редкая БД'], missing: ['вилка до'] })),
}))

describe('NeedForm text import', () => {
  it('fills the form from vacancy text and shows what is missing', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><NeedForm /></MemoryRouter></QueryClientProvider>)
    await userEvent.type(screen.getByLabelText(/текст вакансии/i), 'Ищем Python-разработчика middle, удалёнка')
    await userEvent.click(screen.getByRole('button', { name: /заполнить по тексту/i }))
    expect(await screen.findByDisplayValue('Python-разработчик')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL ×')).toBeInTheDocument()
    expect(screen.getByLabelText('Middle')).toBeChecked()
    expect(screen.getByText(/Не нашли в тексте: вилка до/)).toBeInTheDocument()
    expect(screen.getByText(/Нет в словаре стека: редкая БД/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /сохранить/i })).toBeDisabled()
  })

  it('limits the vacancy text to what the server accepts', () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><NeedForm /></MemoryRouter></QueryClientProvider>)
    expect(screen.getByLabelText(/текст вакансии/i)).toHaveAttribute('maxlength', '8000')
  })
})
