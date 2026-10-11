import { api } from './client'

export type GrossNet = 'gross' | 'net'
export type ContactMethod = 'chat' | 'email' | 'phone'
export type ContactStatus = 'sent' | 'viewed' | 'accepted' | 'declined' | 'countered' | 'offer_v2' | 'company_declined' | 'expired' | 'withdrawn' | 'revoked' | 'conditionally_accepted'
export type DeclineReason = 'salary' | 'format' | 'stack' | 'not_looking' | 'company' | 'spam' | 'other'
export type CompanyBrief = { id: string; name: string; industry: string | null; description: string | null; trust_level: string }
export type InvitationGroup = { team_name: string; size: number; min_size: number; deadline: string; state: string; min_reached_now: boolean | null }
export type Invitation = {
  id: string; status: ContactStatus; version: number; company: CompanyBrief; need_title: string; salary_from: number; salary_to: number
  gross_net: GrossNet; salary_to_net: number; description: string; why_you: string; next_step: string; contact_method: ContactMethod
  expires_at: string; counter_amount: number | null; counter_expires_at: string | null; created_at: string; chat_open: boolean
  hours_per_week?: number | null
  group?: InvitationGroup | null  // командное приглашение: только своё место, без состава и чужих ответов
}
export type EmployerInvitation = {
  id: string; status: ContactStatus; version: number; ref: string; alias: string; salary_from: number; salary_to: number; gross_net: GrossNet
  expires_at: string; counter_amount: number | null; counter_comment: string | null; counter_expires_at: string | null
  decline_reason: string | null; created_at: string; chat_open: boolean; viewed: boolean
  hours_per_week?: number | null
}
export type InviteDraft = {
  ref: string; alias: string; salary_from: number; salary_to: number; gross_net: GrossNet; description: string; why_you: string
  next_step: string; contact_method: ContactMethod; quota_used: number; quota_limit: number
  minor_hours_limit?: number | null  // кандидату нет 18: предел часов в неделю (ст. 92 ТК РФ)
}
export type InviteInput = Omit<InviteDraft, 'alias' | 'quota_used' | 'quota_limit' | 'minor_hours_limit'> & { hours_per_week?: number | null }
export type ChatMessage = { id: number; mine: boolean; author: 'candidate' | 'company'; text: string; at: string }
export type ContactPage = {
  id: string; status: ContactStatus; role: 'candidate' | 'employer'; company: CompanyBrief; need_title: string; alias: string
  candidate: { full_name: string | null; email: string; contacts: Record<string, string> } | null; chat_open: boolean; messages: ChatMessage[]
}
export type Notifications = { items: { id: number; kind: string; title: string; link: string | null; created_at: string; read: boolean }[]; unread: number }

export const STATUS_TITLE: Record<ContactStatus, string> = {
  sent: 'отправлено', viewed: 'просмотрено', accepted: 'принято', declined: 'отклонено', countered: 'встречное условие',
  offer_v2: 'обновлённое приглашение', company_declined: 'отклонено компанией', expired: 'истекло', withdrawn: 'отозвано', revoked: 'контакты скрыты',
  conditionally_accepted: 'условное согласие',
}
export const DECLINE_TITLE: Record<DeclineReason, string> = {
  salary: 'не подходит вилка', format: 'не подходит формат работы', stack: 'не мой стек', not_looking: 'сейчас не ищу работу',
  company: 'не интересна компания', spam: 'спам или не соответствует описанию', other: 'другая причина',
}
export const ACTIVE: ContactStatus[] = ['sent', 'viewed', 'countered', 'offer_v2', 'conditionally_accepted']
export const rub = (n: number) => `${n.toLocaleString('ru-RU')} ₽`

export const getInviteDraft = (needId: string, ref: string) => api<InviteDraft>(`/employer/needs/${needId}/invitations/draft?ref=${encodeURIComponent(ref)}`)
export const sendInvitation = (needId: string, body: InviteInput) => api<EmployerInvitation>(`/employer/needs/${needId}/invitations`, { method: 'POST', body })
export const getNeedInvitations = (needId: string) => api<EmployerInvitation[]>(`/employer/needs/${needId}/invitations`)
export const getQuota = (needId: string) => api<{ used: number; limit: number }>(`/employer/needs/${needId}/quota`)
export const respondCounter = (id: string, body: { action: 'offer_v2' | 'decline'; salary_from?: number; salary_to?: number }) =>
  api<EmployerInvitation>(`/employer/invitations/${id}/counter-response`, { method: 'POST', body })
export const withdrawInvitation = (id: string) => api<EmployerInvitation>(`/employer/invitations/${id}/withdraw`, { method: 'POST' })
export const getMyInvitations = () => api<Invitation[]>('/candidate/invitations')
export const viewInvitation = (id: string) => api<Invitation>(`/candidate/invitations/${id}`)
export const acceptInvitation = (id: string) => api<Invitation>(`/candidate/invitations/${id}/accept`, { method: 'POST', body: { consent_contact_transfer: true } })
export const declineInvitation = (id: string, reason: DeclineReason, comment?: string) =>
  api<Invitation>(`/candidate/invitations/${id}/decline`, { method: 'POST', body: { reason, comment: comment || null } })
export const counterInvitation = (id: string, amount: number, gross_net: GrossNet, comment?: string) =>
  api<Invitation>(`/candidate/invitations/${id}/counter`, { method: 'POST', body: { amount, gross_net, comment: comment || null } })
export const revokeContacts = (id: string) => api<Invitation>(`/candidate/invitations/${id}/revoke`, { method: 'POST' })
export const blockCompany = (companyId: string) => api<void>(`/candidate/blocks/${companyId}`, { method: 'PUT' })
export const unblockCompany = (companyId: string) => api<void>(`/candidate/blocks/${companyId}`, { method: 'DELETE' })
export const getBlocks = () => api<CompanyBrief[]>('/candidate/blocks')
export const getContact = (id: string) => api<ContactPage>(`/contacts/${id}`)
/** Только переписка, без ПДн и без записи в аудит — для опроса чата. */
export const getMessages = (id: string) => api<ChatMessage[]>(`/contacts/${id}/messages`)
export const postMessage = (id: string, text: string) => api<ChatMessage>(`/contacts/${id}/messages`, { method: 'POST', body: { text } })
export const getNotifications = () => api<Notifications>('/notifications')
export const readNotifications = () => api<void>('/notifications/read', { method: 'POST' })
