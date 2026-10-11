import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import CompanyForm from '../pages/employer/CompanyForm'

const h = vi.hoisted(() => ({
  company: { id: 'k1', name: 'Корп', description: null, industry: null, contacts: {}, trust_level: 'L0', domain: null, legal_name: null, l3_pending: false } as Record<string, unknown>,
  verifyDomain: vi.fn(async () => ({})),
  verifyInn: vi.fn(async (_inn: string) => ({})),
  requestL3: vi.fn(async (_comment: string) => ({})),
}))
vi.mock('../api/employer', async (orig) => ({ ...(await orig<typeof import('../api/employer')>()), getCompany: vi.fn(async () => h.company) }))
vi.mock('../api/integrations', () => ({ getIntegrations: vi.fn(async () => ({ endpoints: [], deliveries: [], mock_available: false })) }))
vi.mock('../api/trust', () => ({
  verifyDomain: () => h.verifyDomain(), verifyInn: (inn: string) => h.verifyInn(inn), requestL3: (c: string) => h.requestL3(c),
}))

const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><CompanyForm /></MemoryRouter></QueryClientProvider>)
const level = (l: string, extra: Record<string, unknown> = {}) => { h.company = { ...h.company, trust_level: l, ...extra } }

describe('company trust levels', () => {
  beforeEach(() => { vi.clearAllMocks(); h.company = { ...h.company, trust_level: 'L0', domain: null, legal_name: null, l3_pending: false } })

  it('L0: only the domain step is open and a server error is shown as is', async () => {
    h.verifyDomain.mockRejectedValueOnce(new ApiError(409, 'public_domain', 'Публичная почта не подтверждает компанию. Нужна почта на корпоративном домене'))
    setup()
    expect(await screen.findByText(/Уровень доверия: L0/)).toBeInTheDocument()
    expect(screen.getByLabelText('ИНН')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Проверить юрлицо' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Отправить заявку на L3' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить корпоративный домен' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Публичная почта не подтверждает компанию')
  })

  it('L1: checks the legal entity by INN', async () => {
    level('L1', { domain: 'corp.ru' })
    setup()
    const inn = await screen.findByLabelText('ИНН')
    expect(inn).toBeEnabled()
    await userEvent.type(inn, '7701001005')
    await userEvent.click(screen.getByRole('button', { name: 'Проверить юрлицо' }))
    expect(h.verifyInn).toHaveBeenCalledWith('7701001005')
  })

  it('L2: sends an L3 request with a comment; a pending request is shown instead of the button', async () => {
    level('L2', { domain: 'corp.ru', legal_name: 'ООО «Компания 1005»' })
    setup()
    await userEvent.type(await screen.findByLabelText('Комментарий к заявке на L3'), 'Аккредитованная ИТ-компания')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить заявку на L3' }))
    expect(h.requestL3).toHaveBeenCalledWith('Аккредитованная ИТ-компания')
  })

  it('L2 with a pending request says so', async () => {
    level('L2', { l3_pending: true })
    setup()
    expect(await screen.findByText(/заявка на L3 на рассмотрении/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отправить заявку на L3' })).not.toBeInTheDocument()
  })

  it('L3: says the top level is reached and offers no more steps', async () => {
    level('L3', { domain: 'corp.ru', legal_name: 'ООО «Компания 1005»' })
    setup()
    expect(await screen.findByText(/Присвоен высший уровень L3/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отправить заявку на L3' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Комментарий к заявке на L3')).not.toBeInTheDocument()
  })

  it('tells what each level gives and shows the verified legal entity', async () => {
    level('L2', { legal_name: 'ООО «Компания 1005»' })
    setup()
    expect(await screen.findByText('ООО «Компания 1005»')).toBeInTheDocument()
    expect(screen.getByText(/квота приглашений, число потребностей, вес ваших оценок кандидатов, задачи и помощник к собеседованию/i)).toBeInTheDocument()
  })
})
