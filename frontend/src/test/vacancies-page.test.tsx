import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VacanciesPage from '../pages/candidate/VacanciesPage'

const h = vi.hoisted(() => ({
  apply: vi.fn(async (_id: string, _body: unknown) => ({ id: 'a1', status: 'sent' })),
}))
const company = { id: 'k1', name: 'Корп', industry: 'финтех', trust_level: 'L2' }
const vacancy = {
  id: 'v1', need_id: 'n1', title: 'Backend-разработчик', description: 'Платёжная платформа', specialization: 'backend', grades: ['middle'],
  salary_from: 250000, salary_to: 350000, gross_net: 'gross', city: 'Москва', formats: ['remote'], status: 'open', created_at: '2026-10-09T10:00:00Z',
  company, my_application: null,
}
vi.mock('../api/vacancies', async (orig) => ({
  ...(await orig<typeof import('../api/vacancies')>()),
  getVacancies: vi.fn(async () => [vacancy]),
  getApplications: vi.fn(async () => [{
    id: 'a9', status: 'accepted', decline_reason: null, contact_id: 'c1', created_at: '2026-10-09T11:00:00Z',
    vacancy: { ...vacancy, id: 'v9', title: 'Data-инженер' },
  }]),
  applyVacancy: (id: string, body: unknown) => h.apply(id, body),
}))
vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: vi.fn(async () => ({ texts: [{ type: 'contact_transfer', title: 'Согласие на передачу контактов компании', body: 'Текст' }] })),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><VacanciesPage /></MemoryRouter></QueryClientProvider>)

describe('VacanciesPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('applies only with consent №4 and shows the salary range with gross/net', async () => {
    setup()
    expect(await screen.findByText('Backend-разработчик')).toBeInTheDocument()
    expect(screen.getByText(/250 000 ₽ – 350 000 ₽ до вычета/)).toBeInTheDocument()
    expect(screen.getByText('Москва · Удалёнка')).toBeInTheDocument()  // форматы — по-русски, не кодами remote/hybrid
    const apply = screen.getByRole('button', { name: 'Откликнуться' })
    expect(apply).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Сообщение работодателю'), 'Интересна платформа')
    await userEvent.click(await screen.findByLabelText(/Согласие на передачу контактов компании/))
    await userEvent.click(apply)
    expect(h.apply).toHaveBeenCalledWith('v1', { consent_contact_transfer: true, message: 'Интересна платформа' })
  })

  it('sends one application on a double click', async () => {
    let done: (v: { id: string; status: string }) => void = () => {}
    h.apply.mockImplementationOnce(() => new Promise((r) => { done = r }))
    setup()
    await userEvent.click(await screen.findByLabelText(/Согласие на передачу контактов компании/))
    const apply = screen.getByRole('button', { name: 'Откликнуться' })
    await userEvent.dblClick(apply)
    expect(h.apply).toHaveBeenCalledTimes(1)
    done({ id: 'a1', status: 'sent' })
  })

  it('lists my applications and links an accepted one to the chat', async () => {
    setup()
    expect(await screen.findByText('Data-инженер')).toBeInTheDocument()
    expect(screen.getByText(/принят, контакты открыты/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Контакты и чат' })).toHaveAttribute('href', '/contacts/c1')
  })
})
