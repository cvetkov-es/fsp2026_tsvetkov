import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ContactPage from '../pages/ContactPage'

const post = vi.fn<(id: string, text: string) => Promise<object>>(async () => ({}))
vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getContact: vi.fn(async () => ({ id: 'k1', status: 'accepted', role: 'employer', need_title: 'Бэкенд', alias: 'B-M-ABCD',
    company: { id: 'c1', name: 'Корп', industry: null, description: null, trust_level: 'L2' },
    candidate: { full_name: 'Иван Петров', email: 'ivan@example.ru', contacts: { telegram: '@ivan' } }, chat_open: true,
    messages: [] })),
  // переписку страница опрашивает отдельным запросом без ПДн — страница с контактами грузится один раз
  getMessages: vi.fn(async () => [{ id: 1, mine: false, author: 'candidate', text: 'Здравствуйте!', at: '2026-10-08T10:00:00Z' }]),
  postMessage: (id: string, text: string) => post(id, text),
}))

describe('ContactPage', () => {
  it('shows revealed contacts to the employer and sends chat messages', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/contacts/k1']}>
      <Routes><Route path="/contacts/:id" element={<ContactPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('Иван Петров')).toBeInTheDocument()
    expect(screen.getByText('telegram: @ivan')).toBeInTheDocument()
    expect(await screen.findByText('Здравствуйте!')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Сообщение'), 'Созвонимся завтра?')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(post).toHaveBeenCalledWith('k1', 'Созвонимся завтра?')
  })
})
