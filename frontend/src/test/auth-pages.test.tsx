import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import HomePage from '../pages/HomePage'
import RegisterPage from '../pages/RegisterPage'

vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ me: null, isLoading: false, login: vi.fn() }) }))

describe('Вход и регистрация', () => {
  it('anonymous home is the login screen with FSP ID first', () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Компании приходят к вам с предложением.' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Войти через FSP ID' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Регистрация' })).toHaveAttribute('href', '/register')
    expect(screen.getByRole('link', { name: 'Вход' })).toHaveAttribute('aria-current', 'page')
  })

  it('registration keeps the same shell and marks its tab', () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><RegisterPage /></MemoryRouter></QueryClientProvider>)
    expect(screen.getByRole('link', { name: 'Регистрация' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('group', { name: 'Кто вы' })).toBeInTheDocument()
  })
})
