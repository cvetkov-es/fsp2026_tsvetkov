import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '../api/client'

afterEach(() => vi.restoreAllMocks())

describe('api client', () => {
  it('sends csrf header and credentials, returns json', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: 1 }), { status: 200, headers: { 'content-type': 'application/json' } }),
    )
    const data = await api<{ ok: number }>('/auth/login', { method: 'POST', body: { a: 1 } })
    expect(data.ok).toBe(1)
    const [url, init] = spy.mock.calls[0]
    expect(url).toBe('/api/v1/auth/login')
    expect((init as RequestInit).credentials).toBe('include')
    expect(((init as RequestInit).headers as Record<string, string>)['X-Requested-With']).toBe('fsp')
  })

  it('throws ApiError with problem fields', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ code: 'email_taken', title: 'Занято', status: 409 }), {
        status: 409, headers: { 'content-type': 'application/problem+json' },
      }),
    )
    await expect(api('/auth/register', { method: 'POST', body: {} })).rejects.toMatchObject({
      code: 'email_taken', status: 409,
    } satisfies Partial<ApiError>)
  })
})
