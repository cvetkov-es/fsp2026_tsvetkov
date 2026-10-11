import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MyCases from '../components/candidate/MyCases'

const h = vi.hoisted(() => ({ cases: [] as object[] }))
vi.mock('../api/complaints', () => ({ getMyCases: vi.fn(async () => h.cases) }))

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MyCases /></QueryClientProvider>)

describe('My cases', () => {
  it('shows the status, the answer deadline and the moderator outcome with the text', async () => {
    h.cases = [
      { id: '1', type: 'art16', type_title: 'Возражение по ст. 16 152-ФЗ', status: 'open', created_at: '2026-10-09T10:00:00Z', due_at: '2026-11-08T10:00:00Z', outcome: null, resolution_text: null },
      { id: '2', type: 'item_problem', type_title: 'Проблема в задании теста', status: 'resolved', created_at: '2026-10-01T10:00:00Z', due_at: null, outcome: 'Снять семейство с выдачи', resolution_text: 'Ключ действительно неверен' },
    ]
    show()
    expect(await screen.findByText('Возражение по ст. 16 152-ФЗ')).toBeInTheDocument()
    expect(screen.getByText(/на рассмотрении · ответ до 08.11.2026/)).toBeInTheDocument()
    expect(screen.getByText(/рассмотрено · Снять семейство с выдачи/)).toBeInTheDocument()
    expect(screen.getByText(/Ключ действительно неверен/)).toBeInTheDocument()
  })

  it('stays quiet when there are no cases', async () => {
    h.cases = []
    show()
    expect(await screen.findByText('Обращений пока нет.')).toBeInTheDocument()
  })
})
