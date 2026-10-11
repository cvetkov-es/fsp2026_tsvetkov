import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RegisterForm, type ConsentText } from '../pages/RegisterPage'

const texts: ConsentText[] = [
  { type: 'processing', version: 'v1', title: 'Согласие на обработку персональных данных', body: 'Тело согласия на обработку' },
  { type: 'distribution', version: 'v1', title: 'Согласие на распространение данных профиля', body: 'Тело согласия на распространение' },
]

describe('RegisterForm consent texts', () => {
  it('shows the full text of each consent the user is asked to give', () => {
    render(<MemoryRouter><RegisterForm onSubmit={vi.fn()} texts={texts} /></MemoryRouter>)
    expect(screen.getByText('Тело согласия на обработку')).toBeInTheDocument()
    expect(screen.getByText('Тело согласия на распространение')).toBeInTheDocument()
  })
})
