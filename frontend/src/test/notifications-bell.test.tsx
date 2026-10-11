import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { NotificationsBell } from '../components/NotificationsBell'

const read = vi.fn(async () => undefined)
vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getNotifications: vi.fn(async () => ({ unread: 2, items: [{ id: 1, kind: 'invitation', title: 'Новое приглашение от компании «Корп»', link: '/candidate/invitations', created_at: '', read: false }] })),
  readNotifications: () => read(),
}))

describe('NotificationsBell', () => {
  it('shows unread count, lists notifications and marks them read on open', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><NotificationsBell /></MemoryRouter></QueryClientProvider>)
    const bell = await screen.findByRole('button', { name: 'Уведомления: 2 непрочитанных' })
    await userEvent.click(bell)
    expect(screen.getByRole('link', { name: 'Новое приглашение от компании «Корп»' })).toHaveAttribute('href', '/candidate/invitations')
    expect(read).toHaveBeenCalled()
  })
})
