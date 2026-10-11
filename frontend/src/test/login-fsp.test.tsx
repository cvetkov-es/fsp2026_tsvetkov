import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import LoginPage from '../pages/LoginPage'

vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ login: vi.fn() }) }))

describe('LoginPage', () => {
  it('offers FSP ID login and explains FSP errors from the redirect', () => {
    render(<MemoryRouter initialEntries={['/login?fsp_error=fsp_already_linked']}><LoginPage /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Войти через FSP ID' })).toHaveAttribute('href', '/api/v1/auth/fsp/start?purpose=login')
    expect(screen.getByText('Этот FSP ID уже привязан к другому аккаунту')).toBeInTheDocument()
  })
})
