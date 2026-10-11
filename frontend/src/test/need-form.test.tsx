import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { NeedFormView } from '../pages/employer/NeedForm'

vi.mock('../api/employer', async (orig) => ({ ...(await orig<typeof import('../api/employer')>()), getStackDict: vi.fn(async () => [{ canonical: 'Python', category: 'lang' }]) }))

describe('NeedFormView', () => {
  it('requires title, grade and salary fork before submit', async () => {
    const onSubmit = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><NeedFormView onSubmit={onSubmit} /></MemoryRouter></QueryClientProvider>)
    const submit = screen.getByRole('button', { name: /сохранить/i })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/название/i), 'Бэкенд')
    await userEvent.click(screen.getByLabelText('Middle'))
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/вилка от/i), '200000')
    await userEvent.type(screen.getByLabelText(/вилка до/i), '300000')
    expect(submit).toBeEnabled()
  })
})
