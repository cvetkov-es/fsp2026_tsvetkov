import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import ThreatModelPage from '../pages/ThreatModelPage'

describe('ThreatModelPage', () => {
  it('covers the webhook SSRF threat next to the test threats', () => {
    render(<MemoryRouter><ThreatModelPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Модель угроз: тест и интеграции' })).toBeInTheDocument()
    expect(screen.getByText(/Вебхук как путь во внутреннюю сеть \(SSRF\)/)).toBeInTheDocument()
    expect(screen.getByText(/Принимаем только https-адреса, которые не ведут во внутреннюю сеть/)).toBeInTheDocument()
    expect(screen.getByText(/В событиях только псевдонимы, персональных данных нет/)).toBeInTheDocument()
  })
})
