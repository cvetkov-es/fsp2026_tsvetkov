import { api } from './client'

export type Junior = {
  minor: boolean; age: number | null; status: 'adult' | 'draft' | 'active'; guardian_email: string | null
  hours_limit_vacation: number | null; hours_limit_school: number | null
}
export type GuardianPage = { title: string; body: string; candidate_email: string; guardian_email: string | null }

export const getJunior = () => api<Junior>('/candidate/junior')
export const requestGuardian = (email: string) =>
  api<{ status: string; guardian_url: string | null }>('/candidate/junior/guardian', { method: 'POST', body: { email } })
export const getGuardianPage = (token: string) => api<GuardianPage>(`/guardian/${token}`)
export const acceptGuardian = (token: string, guardian_name: string) =>
  api<{ status: string }>(`/guardian/${token}`, { method: 'POST', body: { accept: true, guardian_name } })
