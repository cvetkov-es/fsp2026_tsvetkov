import { api } from './client'
import type { InviteInput } from './contacts'

export type MySubmission = { status: string; comment: string | null }
export type FeedTask = {
  id: string; title: string; text: string; specialization: string; deadline: string; has_reference: boolean
  answer_max: number
  company: { name: string; trust_level: string }; my_submission: MySubmission | null
}
export type CompanyTask = { id: string; title: string; specialization: string; deadline: string; status: 'open' | 'closed' | 'removed'; submissions: number; pending: number }
export type LlmHint = { fits: 'yes' | 'partly' | 'no'; summary: string; model?: string }
export type Submission = {
  id: string; alias: string; ref: string; answer: string; auto_correct: boolean | null; verdict: 'accepted' | 'rejected' | null
  comment: string | null; llm_hint: LlmHint | null; created_at: string
}
export type TaskSubmissions = {
  task: { id: string; title: string; text: string; reference_answer: string | null; answer_kind: string | null; deadline: string; status: string }
  items: Submission[]
}
export type TaskInput = {
  title: string; specialization: 'backend' | 'frontend' | 'data'; text: string; deadline: string
  reference_answer?: string | null; answer_kind?: 'number' | 'text' | null
}

export const SUBMISSION_STATUS: Record<string, string> = {
  pending: 'на проверке', auto_correct: 'совпадает с эталоном', auto_wrong: 'не совпадает с эталоном', accepted: 'принято', rejected: 'не принято',
}
export const TASK_STATUS: Record<string, string> = { open: 'открыта', closed: 'закрыта по сроку', removed: 'снята модератором' }
export const HINT_FITS: Record<string, string> = { yes: 'решение отвечает условию', partly: 'решение отвечает частично', no: 'решение не отвечает условию' }

export const getTasks = (specialization?: string) =>
  api<FeedTask[]>(`/candidate/tasks${specialization ? `?specialization=${specialization}` : ''}`)
export const submitTask = (id: string, answer: string) => api<MySubmission>(`/candidate/tasks/${id}/submission`, { method: 'POST', body: { answer } })
export const complainTask = (id: string, comment: string) => api<{ ok: boolean }>(`/candidate/tasks/${id}/complaint`, { method: 'POST', body: { comment } })

export const createTask = (body: TaskInput) => api<{ id: string }>('/employer/tasks', { method: 'POST', body })
export const getTaskLimits = () => api<{ text_max: number; ttl_days: number }>('/employer/tasks/limits')
export const getCompanyTasks = () => api<CompanyTask[]>('/employer/tasks')
export const getTaskSubmissions = (id: string) => api<TaskSubmissions>(`/employer/tasks/${id}/submissions`)
export const evaluateSubmission = (id: string, body: { verdict: 'accepted' | 'rejected'; comment: string }) =>
  api<Submission>(`/employer/task-submissions/${id}/evaluate`, { method: 'POST', body })
export const hintSubmission = (id: string) => api<Submission>(`/employer/task-submissions/${id}/hint`, { method: 'POST' })
export const inviteAuthor = (id: string, body: InviteInput & { need_id: string }) =>
  api<{ contact_id: string }>(`/employer/task-submissions/${id}/invite`, { method: 'POST', body })
