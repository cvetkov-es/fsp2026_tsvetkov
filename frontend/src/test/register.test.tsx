import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RegisterForm } from '../pages/RegisterPage'

describe('RegisterForm', () => {
  it('submit disabled until processing consent and visibility preset chosen', async () => {
    const onSubmit = vi.fn()
    render(<MemoryRouter><RegisterForm onSubmit={onSubmit} /></MemoryRouter>)
    const submit = screen.getByRole('button', { name: /зарегистрироваться/i })
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.ru')
    await userEvent.type(screen.getByLabelText(/пароль/i), 'password123')
    await userEvent.type(screen.getByLabelText(/дата рождения/i), '2000-01-15')
    expect(submit).toBeDisabled()
    await userEvent.click(screen.getByLabelText(/согласие на обработку/i))
    expect(submit).toBeDisabled()
    await userEvent.click(screen.getByLabelText(/стандартная видимость/i))
    expect(submit).toBeEnabled()
    await userEvent.click(submit)
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ birth_date: '2000-01-15' }))
  })
})
