import type { Grade, Specialization } from './assessment'
import { api, apiUpload } from './client'
import type { Format, StackItem } from './employer'

export type Details = {
  full_name: string | null; contacts: Record<string, string>; experience_years: number | null; formats: Format[]
  city: string | null; domains: string[]; salary_threshold: number | null; salary_gross_net: 'gross' | 'net'; open_until: string | null
}
// declared — ровно то, что заявил кандидат; items — с подтверждениями и implies
export type StackState = { items: StackItem[]; declared: string[]; unknown: string[] }
export const getDetails = () => api<Details>('/candidate/profile/details')
export const saveDetails = (d: Omit<Details, 'open_until'>) => api<Details>('/candidate/profile/details', { method: 'PUT', body: d })
export const getStack = () => api<StackState>('/candidate/profile/stack')
export const saveStack = (techs: string[]) => api<StackState>('/candidate/profile/stack', { method: 'PUT', body: { techs } })
export const openWindow = () => api<{ open_until: string }>('/candidate/profile/open-window', { method: 'POST' })
export const getMarket = () => api<{ median_net: number | null; n: number }>('/candidate/market')
export type ResumeDraft = {
  source: 'llm' | 'rules'; specialization: Specialization | null; recommended_grade: Grade | null
  experience_years: number | null; stack: string[]; unknown_terms: string[]; formats: Format[]; city: string | null
  domains: string[]; full_name: string | null; contacts: Record<string, string>; warnings: string[]
}
export function uploadResume(file: File) {
  const form = new FormData()
  form.append('file', file)
  return apiUpload<ResumeDraft>('/candidate/profile/resume', form)
}
export const PROFILE_PDF_URL = '/api/v1/candidate/profile/pdf'
