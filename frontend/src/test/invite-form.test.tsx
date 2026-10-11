import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { getInviteDraft } from '../api/contacts'
import { InviteForm } from '../components/employer/InviteForm'

const send = vi.fn<(needId: string, body: unknown) => Promise<object>>(async () => ({}))
vi.mock('../api/contacts', async (orig) => ({
  ...(await orig<typeof import('../api/contacts')>()),
  getInviteDraft: vi.fn(async () => ({ ref: 'abcd1234', alias: 'B-M-ABCD', salary_from: 250000, salary_to: 350000, gross_net: 'gross',
    description: 'Платежи', why_you: 'Middle подтверждён тестом', next_step: 'Созвон', contact_method: 'chat', quota_used: 2, quota_limit: 3 })),
  sendInvitation: (needId: string, body: unknown) => send(needId, body),
}))

describe('InviteForm', () => {
  it('shows why there is no draft instead of preparing it forever', async () => {
    vi.mocked(getInviteDraft).mockRejectedValueOnce(new ApiError(404, 'candidate_not_found', 'Кандидата нет в подборке этой потребности'))
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><InviteForm needId="n1" cardRef="zzzz" onSent={vi.fn()} /></QueryClientProvider>)
    expect(await screen.findByRole('alert')).toHaveTextContent('Кандидата нет в подборке этой потребности')
    expect(screen.queryByText(/готовим черновик/i)).not.toBeInTheDocument()
  })


  it('uses the given send instead of the plain invitation (invite the task author)', async () => {
    send.mockClear()
    const custom = vi.fn<(v: unknown) => Promise<unknown>>(async () => ({}))
    const onSent = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}><InviteForm needId="n1" cardRef="abcd1234" send={custom} onSent={onSent} /></QueryClientProvider>)
    await userEvent.click(await screen.findByRole('button', { name: /отправить приглашение/i }))
    expect(custom).toHaveBeenCalledWith(expect.objectContaining({ ref: 'abcd1234' }))
    expect(send).not.toHaveBeenCalled()
    expect(onSent).toHaveBeenCalled()
  })

  it('is prefilled from the need and explanation, shows quota and sends', async () => {
    const onSent = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}><InviteForm needId="n1" cardRef="abcd1234" onSent={onSent} /></QueryClientProvider>)
    expect(await screen.findByDisplayValue('Middle подтверждён тестом')).toBeInTheDocument()
    expect(screen.getByText(/свободно в квоте: 1 из 3/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /отправить приглашение/i }))
    expect(send).toHaveBeenCalledWith('n1', expect.objectContaining({ ref: 'abcd1234', salary_to: 350000, gross_net: 'gross' }))
    expect(onSent).toHaveBeenCalled()
  })
})
