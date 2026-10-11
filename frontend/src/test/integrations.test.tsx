import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import IntegrationsBlock from '../components/employer/IntegrationsBlock'

const h = vi.hoisted(() => ({
  data: null as unknown,
  create: vi.fn(async (_url: string) => ({ id: 'e2', url: 'https://ats.example.com/hook', secret: 'whsec_SECRETVALUE' })),
  connect: vi.fn(async () => ({ id: 'm1', url: 'http://localhost:5173/mock/ats/m1/webhook', secret: 'whsec_MOCKSECRET', page: 'http://localhost:5173/mock/ats/m1' })),
  ping: vi.fn(async (_id: string) => ({ queued: true })),
  remove: vi.fn(async (_id: string) => undefined),
}))
vi.mock('../api/integrations', async (orig) => ({
  ...(await orig<typeof import('../api/integrations')>()),
  getIntegrations: vi.fn(async () => h.data),
  createWebhook: (u: string) => h.create(u), connectMockAts: () => h.connect(),
  pingWebhook: (id: string) => h.ping(id), deleteWebhook: (id: string) => h.remove(id),
}))

const data = (over: object = {}) => ({
  endpoints: [{ id: 'e1', url: 'https://ats.example.com/hook', created_at: '2026-10-09T10:00:00Z' }],
  deliveries: [
    { id: 2, endpoint_id: 'e1', event_type: 'contact.accepted', at: '2026-10-09T10:05:00Z', status: 'failed', status_code: 500, attempt: 5, error: 'HTTP 500' },
    { id: 1, endpoint_id: 'e1', event_type: 'contact.sent', at: '2026-10-09T10:01:00Z', status: 'delivered', status_code: 200, attempt: 0, error: null },
  ],
  mock_available: true, ...over,
})
const setup = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><IntegrationsBlock /></QueryClientProvider>)

describe('integrations (ATS)', () => {
  beforeEach(() => { vi.clearAllMocks(); h.data = data() })

  it('lists the webhooks and the delivery journal with status, code and attempt', async () => {
    setup()
    expect(await screen.findByText('https://ats.example.com/hook')).toBeInTheDocument()
    expect(screen.getByText(/contact\.accepted/)).toBeInTheDocument()
    expect(screen.getByText(/не доставлено · код 500 · попытка 5/)).toBeInTheDocument()
    expect(screen.getByText(/доставлено · код 200/)).toBeInTheDocument()
  })

  it('creates a webhook and shows the secret once with a warning', async () => {
    setup()
    await userEvent.type(await screen.findByLabelText('Адрес (https)'), 'https://ats.example.com/hook')
    await userEvent.click(screen.getByRole('button', { name: 'Добавить вебхук' }))
    expect(h.create).toHaveBeenCalledWith('https://ats.example.com/hook')
    expect(await screen.findByText('whsec_SECRETVALUE')).toBeInTheDocument()
    expect(screen.getByText(/Сохраните секрет: он больше не покажется/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Секрет сохранён' }))
    expect(screen.queryByText('whsec_SECRETVALUE')).not.toBeInTheDocument()
  })

  it('shows the server refusal of a private address', async () => {
    h.create.mockRejectedValueOnce(new ApiError(422, 'webhook_url_private', 'Адрес вебхука ведёт во внутреннюю сеть'))
    setup()
    await userEvent.type(await screen.findByLabelText('Адрес (https)'), 'https://10.0.0.5/hook')
    await userEvent.click(screen.getByRole('button', { name: 'Добавить вебхук' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Адрес вебхука ведёт во внутреннюю сеть')
  })

  it('pings and disconnects a webhook', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Проверить (ping)' }))
    expect(h.ping).toHaveBeenCalledWith('e1')
    await userEvent.click(screen.getByRole('button', { name: 'Отключить' }))
    expect(h.remove).toHaveBeenCalledWith('e1')
  })

  it('connects the demo mock ATS and links to its page; the button is hidden when mocks are off', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Подключить демо-ATS' }))
    expect(h.connect).toHaveBeenCalled()
    expect(await screen.findByRole('link', { name: 'Страница демо-ATS' })).toHaveAttribute('href', 'http://localhost:5173/mock/ats/m1')
    expect(screen.getByText('whsec_MOCKSECRET')).toBeInTheDocument()
  })

  it('has no mock button when the mock is not available', async () => {
    h.data = data({ mock_available: false })
    setup()
    await screen.findByText('https://ats.example.com/hook')
    expect(screen.queryByRole('button', { name: 'Подключить демо-ATS' })).not.toBeInTheDocument()
  })
})
