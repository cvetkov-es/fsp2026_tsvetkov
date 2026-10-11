import { api } from './client'
import { rub } from './contacts'
import type { Card } from './employer'

export type Vacancy = {
  id: string; need_id: string; title: string; description: string; specialization: string; grades: string[]
  salary_from: number; salary_to: number; gross_net: 'gross' | 'net'; city: string | null; formats: string[]
  status: 'open' | 'closed'; created_at: string
  company: { id: string; name: string; industry: string | null; trust_level: string }
  my_application: { status: string; contact_id: string | null } | null
}
export type MyApplication = {
  id: string; status: string; decline_reason: string | null; contact_id: string | null; created_at: string; vacancy: Vacancy
}
export type VacancyApplication = {
  id: string; alias: string; ref: string; message: string; status: string; decline_reason: string | null
  contact_id: string | null; created_at: string; card: Card | null
  minor_hours_limit?: number | null  // кандидату нет 18: предел часов в неделю при принятии отклика
}
export type DeclineReason = 'stack' | 'level' | 'salary' | 'filled' | 'other'

export const APPLICATION_STATUS: Record<string, string> = {
  sent: 'отправлен', viewed: 'просмотрен', accepted: 'принят, контакты открыты', declined: 'отклонён',
}
export const APPLICATION_DECLINE: Record<DeclineReason, string> = {
  stack: 'не подходит стек', level: 'не подходит уровень', salary: 'не сошлись по вилке', filled: 'место занято', other: 'другая причина',
}

export const salary = (v: Pick<Vacancy, 'salary_from' | 'salary_to' | 'gross_net'>) =>
  `${rub(v.salary_from)} – ${rub(v.salary_to)} ${v.gross_net === 'gross' ? 'до вычета' : 'на руки'}`

export const getVacancies = (specialization?: string) =>
  api<Vacancy[]>(`/candidate/vacancies${specialization ? `?specialization=${specialization}` : ''}`)
export const applyVacancy = (id: string, body: { consent_contact_transfer: boolean; message: string }) =>
  api<{ id: string; status: string }>(`/candidate/vacancies/${id}/apply`, { method: 'POST', body })
export const getApplications = () => api<MyApplication[]>('/candidate/applications')

export const publishVacancy = (needId: string, description: string) =>
  api<Vacancy>(`/employer/needs/${needId}/vacancy`, { method: 'POST', body: { description } })
export const getCompanyVacancies = () => api<Vacancy[]>('/employer/vacancies')
export const closeVacancy = (id: string) => api<Vacancy>(`/employer/vacancies/${id}/close`, { method: 'POST' })
export const getVacancyApplications = (id: string) => api<VacancyApplication[]>(`/employer/vacancies/${id}/applications`)
export const acceptApplication = (id: string, hours_per_week?: number) =>
  api<{ contact_id: string }>(`/employer/applications/${id}/accept`, { method: 'POST', body: hours_per_week === undefined ? undefined : { hours_per_week } })
export const declineApplication = (id: string, reason: DeclineReason) =>
  api<{ id: string; status: string }>(`/employer/applications/${id}/decline`, { method: 'POST', body: { reason } })
