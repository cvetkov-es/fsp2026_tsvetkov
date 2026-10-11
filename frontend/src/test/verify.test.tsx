import { render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import VerifyPage from '../pages/VerifyPage'

afterEach(() => vi.restoreAllMocks())

describe('VerifyPage', () => {
  it('sends the single-use token once even under StrictMode', async () => {
    let calls = 0
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      calls += 1
      return calls === 1
        ? new Response(null, { status: 204 })
        : new Response(JSON.stringify({ code: 'token_invalid', title: 'Ссылка недействительна или уже использована', status: 400 }), {
            status: 400, headers: { 'content-type': 'application/problem+json' },
          })
    })
    render(<StrictMode><MemoryRouter initialEntries={['/verify?token=abc']}><VerifyPage /></MemoryRouter></StrictMode>)
    expect(await screen.findByText(/почта подтверждена/i)).toBeInTheDocument()
    expect(spy).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/недействительна/i)).not.toBeInTheDocument()
  })
})
