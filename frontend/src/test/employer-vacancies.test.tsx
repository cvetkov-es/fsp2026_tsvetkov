import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import VacanciesPage from '../pages/employer/VacanciesPage'

const h = vi.hoisted(() => ({
  publish: vi.fn(async (_needId: string, _description: string) => ({})),
  accept: vi.fn(async (_id: string, _hours?: number) => ({ contact_id: 'c1' })),
  minorLimit: null as number | null,
  decline: vi.fn(async (_id: string, _reason: string) => ({ id: 'a1', status: 'declined' })),
  close: vi.fn(async (_id: string) => ({})),
}))
vi.mock('../api/employer', async (orig) => ({
  ...(await orig<typeof import('../api/employer')>()),
  listNeeds: vi.fn(async () => [
    { id: 'n1', title: 'Бэкенд', status: 'active' },
    { id: 'n2', title: 'Уже опубликованная', status: 'active' },
    { id: 'n3', title: 'Закрытая', status: 'closed' },
  ]),
}))
vi.mock('../api/vacancies', async (orig) => ({
  ...(await orig<typeof import('../api/vacancies')>()),
  getCompanyVacancies: vi.fn(async () => [{
    id: 'v1', need_id: 'n2', title: 'Уже опубликованная', description: 'Описание', specialization: 'backend', grades: ['middle'],
    salary_from: 250000, salary_to: 350000, gross_net: 'net', city: null, formats: [], status: 'open', created_at: '2026-10-09T10:00:00Z',
    company: { id: 'k1', name: 'Корп', industry: null, trust_level: 'L2' }, my_application: null,
  }]),
  getVacancyApplications: vi.fn(async () => [{
    id: 'a1', alias: 'B-M-AAAA', ref: 'aaaa1111', message: 'Интересна платформа', status: 'viewed', decline_reason: null,
    contact_id: null, created_at: '2026-10-09T11:00:00Z', card: null, minor_hours_limit: h.minorLimit,
  }]),
  publishVacancy: (needId: string, description: string) => h.publish(needId, description),
  acceptApplication: (id: string, hours?: number) => h.accept(id, hours),
  declineApplication: (id: string, reason: string) => h.decline(id, reason),
  closeVacancy: (id: string) => h.close(id),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><VacanciesPage /></MemoryRouter></QueryClientProvider>)

describe('employer VacanciesPage', () => {
  beforeEach(() => { vi.clearAllMocks(); h.minorLimit = null })

  it('publishes a vacancy only from an active need without one', async () => {
    setup()
    const select = await screen.findByLabelText('Потребность для вакансии')
    expect(screen.getByRole('option', { name: 'Бэкенд' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Уже опубликованная' })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Закрытая' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Описание вакансии'), 'Платёжная платформа, команда 6 человек')
    await userEvent.click(screen.getByRole('button', { name: 'Опубликовать вакансию' }))
    expect(select).toHaveValue('n1')
    expect(h.publish).toHaveBeenCalledWith('n1', 'Платёжная платформа, команда 6 человек')
  })

  it('asks for the weekly hours up to the limit when the applicant is under 18', async () => {
    h.minorLimit = 24
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Отклики' }))
    const hours = await screen.findByLabelText('Часов в неделю (до 24)')
    const accept = screen.getByRole('button', { name: 'Принять' })
    expect(accept).toBeDisabled()
    await userEvent.type(hours, '30')
    expect(accept).toBeDisabled()  // сверх лимита
    await userEvent.clear(hours)
    await userEvent.type(hours, '20')
    await userEvent.click(accept)
    expect(h.accept).toHaveBeenCalledWith('a1', 20)
  })

  it('does not ask for hours when the applicant is an adult', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Отклики' }))
    await screen.findByText('B-M-AAAA')
    expect(screen.queryByLabelText(/Часов в неделю/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Принять' }))
    expect(h.accept).toHaveBeenCalledWith('a1', undefined)
  })

  it('reports a failed close instead of ignoring it', async () => {
    h.close.mockRejectedValueOnce(new ApiError(500, 'error', 'Сервер недоступен'))
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Закрыть' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Сервер недоступен')
  })

  it('accepts an application and links the contact and chat; declines with a reason', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Отклики' }))
    expect(await screen.findByText('B-M-AAAA')).toBeInTheDocument()
    expect(screen.getByText('Интересна платформа')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Причина отказа'), 'level')
    await userEvent.click(screen.getByRole('button', { name: 'Отклонить' }))
    expect(h.decline).toHaveBeenCalledWith('a1', 'level')
    await userEvent.click(screen.getByRole('button', { name: 'Принять' }))
    expect(h.accept).toHaveBeenCalledWith('a1', undefined)
    expect(await screen.findByRole('link', { name: 'Контакты и чат' })).toHaveAttribute('href', '/contacts/c1')
  })
})
