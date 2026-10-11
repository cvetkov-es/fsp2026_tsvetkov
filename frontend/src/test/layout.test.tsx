import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { useFocusMode } from '../components/focus-mode'
import Layout from '../components/Layout'

afterEach(() => vi.restoreAllMocks())

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/problem+json' } })
const ME = { id: 'u1', email: 'demo.candidate@fsp-hiring.local', role: 'candidate', is_demo: true, impersonated_by: null }
const PERSONAS = [
  { id: 'u1', email: 'demo.candidate@fsp-hiring.local', role: 'candidate' },
  { id: 'u2', email: 'demo.employer@fsp-hiring.local', role: 'employer' },
  { id: 'u3', email: 'demo.moderator@fsp-hiring.local', role: 'moderator' },
  { id: 'u4', email: 'demo.reviewed@fsp-hiring.local', role: 'candidate' },
]
const show = (path = '/') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AuthProvider>
      <Routes><Route element={<Layout />}><Route index element={<p>главная</p>} /><Route path="*" element={<p>страница</p>} /></Route></Routes>
    </AuthProvider></MemoryRouter>
  </QueryClientProvider>)

function FocusPage() {
  useFocusMode(true)
  return <p>фокус</p>
}

describe('Layout', () => {
  it('a focus-mode page makes the header inert and hidden from assistive tech', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => String(input).endsWith('/auth/me') ? json(ME) : json([]))
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/focus']}><AuthProvider>
        <Routes><Route element={<Layout />}><Route path="/focus" element={<FocusPage />} /></Route></Routes>
      </AuthProvider></MemoryRouter></QueryClientProvider>)
    await screen.findByText('фокус')
    const header = document.querySelector('header')!
    expect(header).toHaveAttribute('inert')
    expect(header).toHaveAttribute('aria-hidden', 'true')
  })

  it('the anonymous home already is the login screen, so the header has no second "Войти"', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => String(input).endsWith('/auth/me') ? json({ code: 'unauthorized', title: 'Нужен вход', status: 401 }, 401) : json([]))
    show('/')
    await screen.findByText('главная')
    expect(screen.queryByRole('link', { name: 'Войти' })).not.toBeInTheDocument()
  })

  it('the profile menu closes on Escape', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => String(input).endsWith('/auth/me') ? json({ ...ME, is_demo: false }) : json([]))
    show('/candidate/skills')
    await userEvent.click(await screen.findByRole('button', { name: 'Меню профиля' }))
    expect(screen.getByRole('button', { name: 'Выйти' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('button', { name: 'Выйти' })).not.toBeInTheDocument()
  })

  it('shows an error when logout fails instead of failing silently', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return json({ ...ME, is_demo: false })
      if (url.endsWith('/demo/personas') || url.endsWith('/candidate/invitations')) return json([])
      return json({ code: 'internal_error', title: 'Ошибка на сервере. Попробуйте позже', status: 500 }, 500)
    })
    show('/candidate/skills')
    await userEvent.click(await screen.findByRole('button', { name: 'Меню профиля' }))
    await userEvent.click(screen.getByRole('button', { name: 'Выйти' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ошибка на сервере. Попробуйте позже')
  })

  it('links the public lab page for everyone, even without login', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input).endsWith('/auth/me')) return json({ code: 'unauthorized', title: 'Нужен вход', status: 401 }, 401)
      return json([])
    })
    show('/lab')
    expect(await screen.findByRole('link', { name: 'Лаборатория' })).toHaveAttribute('href', '/lab')
  })

  it('candidate nav marks the current section and counts invitations awaiting an answer', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return json(ME)
      if (url.endsWith('/candidate/invitations')) {
        return json([{ status: 'sent' }, { status: 'viewed' }, { status: 'offer_v2' }, { status: 'accepted' }, { status: 'countered' }])
      }
      return json([])
    })
    show('/candidate/skills')
    // пункты кандидата появляются, когда загрузился /auth/me
    expect(await screen.findByRole('link', { name: 'Навыки' })).toHaveAttribute('aria-current', 'page')
    const nav = screen.getByRole('navigation', { name: 'Разделы' })
    expect(await within(nav).findByLabelText('ждут ответа: 3')).toHaveTextContent('3')
  })

  it('demo switch logs in as the chosen persona and opens the home page', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return json(ME)
      if (url.endsWith('/demo/personas')) return json(PERSONAS)
      if (url.endsWith('/demo/login-as')) return json({ ...ME, id: 'u2', role: 'employer' })
      return json([])
    })
    show('/candidate/skills')
    const demo = await screen.findByRole('group', { name: 'Демо: войти как' })
    expect(within(demo).getByRole('button', { name: 'Кандидат' })).toHaveAttribute('aria-pressed', 'true')
    const more = screen.getByRole('combobox', { name: 'Другие демо-персоны' })
    expect(within(more).getByRole('option', { name: /Модератор/ })).toBeInTheDocument()
    await userEvent.click(within(demo).getByRole('button', { name: 'Работодатель' }))
    expect(await screen.findByText('главная')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([u]) => String(u).endsWith('/demo/login-as'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ user_id: 'u2' })
  })
})
