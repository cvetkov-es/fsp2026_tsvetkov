import { api } from './client'

export type FspStatus = 'NOT_LINKED' | 'LINKED' | 'LINKED_EMPTY' | 'SYNC_STALE' | 'CONSENT_REVOKED'
export type FspResult = {
  competition_title: string; discipline_title: string; date: string; place: number | null; field_size: number | null
  tier: 'winner' | 'prize' | 'finalist' | 'online' | 'participant'; tier_title: string; team_name: string | null; team_size: number | null
  counted: boolean; note: string | null
}
export type FspProfile = {
  status: FspStatus; summary: string | null; last_sync_at: string | null; results: FspResult[]
  login_via_fsp?: boolean // аккаунт без пароля: FSP ID остаётся способом входа и после отзыва данных
  online: { count: number; disciplines: number }; ranks: { rank: string; title: string; valid_until: string | null; valid: boolean }[]
}
export type TeamMember = { ref: string; alias: string; specialization: string; grade: string | null; grade_status: string; minor?: boolean }
export type FspTeam = {
  team_id: string; team_name: string | null; competition_title: string; discipline_title: string; date: string; place: number | null
  field_size: number | null; tier: string; team_size: number | null; on_platform: number; cohesion: number; members: TeamMember[]
}
type Consents = { processing: boolean; distribution_preset: 'standard' | 'minimal' | null }

// Вход через FSP ID — переход браузера на IdP, а не fetch: обычные ссылки
export const FSP_LOGIN_URL = '/api/v1/auth/fsp/start?purpose=login'
export const FSP_LINK_URL = '/api/v1/auth/fsp/start?purpose=link'

export const getFsp = () => api<FspProfile>('/candidate/fsp')
export const unlinkFsp = () => api<void>('/candidate/fsp', { method: 'DELETE' })
export const getFspPending = (ticket: string) => api<{ email: string | null; name: string | null }>(`/auth/fsp/pending/${encodeURIComponent(ticket)}`)
export const completeFsp = (body: { ticket: string; birth_date: string; consents: Consents }) => api('/auth/fsp/complete', { method: 'POST', body })
export const getTeams = (specialization?: string) => api<FspTeam[]>(`/employer/teams${specialization ? `?specialization=${specialization}` : ''}`)

const FSP_ERRORS: Record<string, string> = {
  access_denied: 'Вход через FSP ID отменён', invalid_request: 'FSP ID вернул неполный ответ. Попробуйте ещё раз',
  login_required: 'Войдите, чтобы привязать FSP ID', fsp_state_invalid: 'Вход через FSP ID устарел. Начните заново',
  fsp_unavailable: 'FSP ID сейчас недоступен. Попробуйте позже', fsp_already_linked: 'Этот FSP ID уже привязан к другому аккаунту',
  fsp_other_linked: 'К аккаунту уже привязан другой FSP ID. Сначала отвяжите его', fsp_token_invalid: 'Ответ FSP ID не прошёл проверку',
  fsp_code_rejected: 'FSP ID не принял код входа. Попробуйте ещё раз',
  fsp_email_unverified: 'FSP ID не подтвердил почту. Зарегистрируйтесь по почте',
  internal: 'Не удалось завершить вход через FSP ID. Попробуйте ещё раз',
}
export const fspErrorText = (code: string | null) => (code ? FSP_ERRORS[code] ?? 'Не удалось войти через FSP ID' : null)
