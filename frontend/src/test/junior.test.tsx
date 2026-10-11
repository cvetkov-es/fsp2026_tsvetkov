import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { Card } from '../api/employer'
import { CandidateCard } from '../components/employer/CandidateCard'
import { InviteForm } from '../components/employer/InviteForm'
import JuniorBlock from '../components/candidate/JuniorBlock'
import GuardianPage from '../pages/GuardianPage'
import { NeedFormView } from '../pages/employer/NeedForm'

const h = vi.hoisted(() => ({
  state: null as unknown,
  request: vi.fn(async (_email: string) => ({ status: 'sent', guardian_url: 'http://localhost:5173/guardian/tok1' as string | null })),
  accept: vi.fn(async (_t: string, _n: string) => ({ status: 'accepted' })),
  send: vi.fn(async (_n: string, _b: unknown) => ({})),
  draft: { ref: 'abcd1234', alias: 'B-M-ABCD', salary_from: 100000, salary_to: 150000, gross_net: 'net', description: '', why_you: 'Подходит',
    next_step: 'Созвон', contact_method: 'chat', quota_used: 0, quota_limit: 3, minor_hours_limit: null as number | null },
}))
vi.mock('../api/junior', () => ({
  getJunior: vi.fn(async () => h.state),
  requestGuardian: (e: string) => h.request(e),
  getGuardianPage: vi.fn(async () => ({ title: 'Согласие законного представителя несовершеннолетнего', body: 'Я, законный представитель…', candidate_email: 'ki***@example.ru', guardian_email: 'mama@example.ru' })),
  acceptGuardian: (t: string, n: string) => h.accept(t, n),
}))
vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getInviteDraft: vi.fn(async () => h.draft),
  sendInvitation: (n: string, b: unknown) => h.send(n, b),
}))
vi.mock('../api/employer', async (orig) => ({ ...(await orig<typeof import('../api/employer')>()), getStackDict: vi.fn(async () => []) }))

const qc = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
const junior = (status: string) => ({ minor: true, age: 15, status, guardian_email: status === 'active' ? 'mama@example.ru' : null, hours_limit_vacation: 24, hours_limit_school: 12 })

describe('junior track in the cabinet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('draft: explains the status, asks for the guardian email and offers the demo link', async () => {
    h.state = junior('draft')
    render(<QueryClientProvider client={qc()}><MemoryRouter><JuniorBlock /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/Работодатели увидят профиль после согласия законного представителя/)).toBeInTheDocument()
    const send = screen.getByRole('button', { name: 'Отправить ссылку представителю' })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Почта законного представителя'), 'mama@example.ru')
    await userEvent.click(send)
    expect(h.request).toHaveBeenCalledWith('mama@example.ru')
    expect(await screen.findByRole('link', { name: 'Открыть страницу согласия (демо)' })).toHaveAttribute('href', '/guardian/tok1')
  })

  it('active: tells what is available and the hour limits', async () => {
    h.state = junior('active')
    render(<QueryClientProvider client={qc()}><MemoryRouter><JuniorBlock /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/Доступны стажировка и каникулярная работа, до 24 ч в неделю в каникулы и до 12 ч в учебный год/)).toBeInTheDocument()
  })

  it('says so when the state could not be loaded instead of staying silent', async () => {
    const { getJunior } = await import('../api/junior')
    vi.mocked(getJunior).mockRejectedValueOnce(new ApiError(500, 'error', 'Сервер недоступен'))
    render(<QueryClientProvider client={qc()}><MemoryRouter><JuniorBlock /></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByRole('alert')).toHaveTextContent('Сервер недоступен')
  })

  it('shows nothing for an adult', async () => {
    h.state = { minor: false, age: null, status: 'adult', guardian_email: null, hours_limit_vacation: null, hours_limit_school: null }
    const { container } = render(<QueryClientProvider client={qc()}><MemoryRouter><JuniorBlock /></MemoryRouter></QueryClientProvider>)
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  })
})

describe('guardian page', () => {
  it('shows the consent text and records the consent with the guardian name', async () => {
    render(<QueryClientProvider client={qc()}><MemoryRouter initialEntries={['/guardian/tok1']}>
      <Routes><Route path="/guardian/:token" element={<GuardianPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('Согласие законного представителя несовершеннолетнего')).toBeInTheDocument()
    expect(screen.getByText(/ki\*\*\*@example\.ru/)).toBeInTheDocument()
    const give = screen.getByRole('button', { name: 'Даю согласие' })
    expect(give).toBeDisabled()
    await userEvent.type(screen.getByLabelText('ФИО законного представителя'), 'Иванова Анна')
    await userEvent.click(give)
    expect(h.accept).toHaveBeenCalledWith('tok1', 'Иванова Анна')
    expect(await screen.findByText(/Спасибо, согласие получено/)).toBeInTheDocument()
  })
})

describe('employment, hours and the minor chip', () => {
  it('need form lets the employer pick the employment kind', async () => {
    const onSubmit = vi.fn()
    render(<QueryClientProvider client={qc()}><MemoryRouter><NeedFormView onSubmit={onSubmit} /></MemoryRouter></QueryClientProvider>)
    await userEvent.type(screen.getByLabelText(/название/i), 'Стажёр')
    await userEvent.click(screen.getByLabelText('Middle'))
    await userEvent.type(screen.getByLabelText(/вилка от/i), '30000')
    await userEvent.type(screen.getByLabelText(/вилка до/i), '40000')
    await userEvent.selectOptions(screen.getByLabelText('Занятость'), 'internship')
    await userEvent.click(screen.getByRole('button', { name: /сохранить/i }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ employment: 'internship' }))
  })

  it('invite form asks for hours up to the limit only for a minor', async () => {
    h.draft = { ...h.draft, minor_hours_limit: 24 }
    const onSent = vi.fn()
    render(<QueryClientProvider client={qc()}><InviteForm needId="n1" cardRef="abcd1234" onSent={onSent} /></QueryClientProvider>)
    const hours = await screen.findByLabelText('Часов в неделю (до 24)')
    const send = screen.getByRole('button', { name: /отправить приглашение/i })
    expect(send).toBeDisabled()
    await userEvent.type(hours, '30')
    expect(send).toBeDisabled()  // сверх лимита
    await userEvent.clear(hours)
    await userEvent.type(hours, '20')
    await userEvent.click(send)
    expect(h.send).toHaveBeenCalledWith('n1', expect.objectContaining({ hours_per_week: 20 }))
  })

  it('invite form has no hours field for an adult', async () => {
    h.draft = { ...h.draft, minor_hours_limit: null }
    render(<QueryClientProvider client={qc()}><InviteForm needId="n1" cardRef="abcd1234" onSent={vi.fn()} /></QueryClientProvider>)
    await screen.findByDisplayValue('Подходит')
    expect(screen.queryByLabelText(/Часов в неделю/)).not.toBeInTheDocument()
  })

  it('card shows the junior chip', () => {
    const card = { ref: 'a1', alias: 'B-M-AAAA', grade: 'middle', grade_status: 'confirmed', block: 1, fit_level: 'high', readiness: null, stack: [], skills: [],
      experience_years: null, formats: [], city: null, conflicts: [], pinned: false, express: false, filter_mismatch: null,
      explanation: { lines: ['Middle подтверждён тестом'], missing: [], counterfactual: null } } as Card
    const { rerender } = render(<CandidateCard card={{ ...card, minor: true }} />)
    expect(screen.getByText('14–17 лет: стажировка или каникулярная работа')).toBeInTheDocument()
    rerender(<CandidateCard card={card} />)
    expect(screen.queryByText(/14–17 лет/)).not.toBeInTheDocument()
  })
})
