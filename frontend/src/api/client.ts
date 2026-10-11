// Без параметров-свойств конструктора: шаблон Vite включает erasableSyntaxOnly
export class ApiError extends Error {
  status: number
  code: string
  title: string
  detail?: string | null
  constructor(status: number, code: string, title: string, detail?: string | null) {
    super(title)
    this.status = status
    this.code = code
    this.title = title
    this.detail = detail
  }
}

type Opts = { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; body?: unknown }

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: opts.method ?? 'GET',
    credentials: 'include',
    headers: { 'X-Requested-With': 'fsp', ...(opts.body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, data.code ?? 'error', data.title ?? 'Ошибка', data.detail)
  return data as T
}

/** multipart/form-data: Content-Type с границей ставит сам браузер, заголовок CSRF — как у api(). */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { method: 'POST', credentials: 'include', headers: { 'X-Requested-With': 'fsp' }, body: form })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, data.code ?? 'error', data.title ?? 'Ошибка', data.detail)
  return data as T
}
