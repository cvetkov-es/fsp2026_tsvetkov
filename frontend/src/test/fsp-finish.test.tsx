import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { getFspPending } from '../api/fsp'
import FspFinishPage from '../pages/FspFinishPage'

const completeFsp = vi.fn<(body: unknown) => Promise<object>>(async () => ({}))
vi.mock('../api/fsp', async (orig) => ({
  ...(await orig<typeof import('../api/fsp')>()),
  getFspPending: vi.fn(async () => ({ email: 'athlete8@athletes.fsp-mock.example', name: 'Иван Демидов' })),
  completeFsp: (body: unknown) => completeFsp(body),
}))
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api: vi.fn(async () => ({ texts: [] })) }))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ refresh: vi.fn(async () => undefined) }) }))

describe('FspFinishPage', () => {
  it('needs birth date and both consents, then completes with the ticket', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/fsp/finish?ticket=t-123456789']}>
      <Routes><Route path="/fsp/finish" element={<FspFinishPage />} /><Route path="/candidate/profile" element={<p>профиль</p>} /></Routes>
    </MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText(/Иван Демидов · athlete8@athletes\.fsp-mock\.example/)).toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Создать аккаунт' })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Дата рождения/), '2000-05-01')
    await userEvent.click(screen.getByLabelText(/обработку персональных данных/))
    await userEvent.click(screen.getByLabelText(/Стандартная видимость/))
    await userEvent.click(submit)
    expect(completeFsp).toHaveBeenCalledWith({ ticket: 't-123456789', birth_date: '2000-05-01', consents: { processing: true, distribution_preset: 'standard' } })
    expect(await screen.findByText('профиль')).toBeInTheDocument()
  })

  it('explains why the ticket cannot create an account', async () => {
    vi.mocked(getFspPending).mockRejectedValueOnce(new ApiError(422, 'fsp_email_unverified', 'FSP ID не подтвердил почту. Зарегистрируйтесь по почте'))
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/fsp/finish?ticket=t-123456789']}>
      <Routes><Route path="/fsp/finish" element={<FspFinishPage />} /></Routes>
    </MemoryRouter></QueryClientProvider>)
    expect(await screen.findByText('FSP ID не подтвердил почту. Зарегистрируйтесь по почте')).toBeInTheDocument()
  })
})
