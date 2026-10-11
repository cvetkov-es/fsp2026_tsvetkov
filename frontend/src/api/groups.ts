import { api } from './client'

export type GroupState = 'open' | 'ended' | 'min_reached' | 'not_reached' | 'closed'
export type GroupMember = { contact_id: string; alias: string; status: string; salary_from: number; salary_to: number; hours_per_week: number | null }
export type Group = {
  id: string; team_name: string; need_id: string; need_title: string; min_size: number; size: number; deadline: string
  state: GroupState; min_reached_now: boolean; members: GroupMember[]
}
export type GroupListItem = { id: string; team_name: string; need_title: string; size: number; deadline: string; state: GroupState }
export type GroupInput = {
  need_id: string; team_id: string; min_size: number; deadline: string
  members: { ref: string; salary_from: number; salary_to: number; hours_per_week?: number }[]
  gross_net: 'gross' | 'net'; description: string; why_you: string; next_step: string; contact_method?: 'chat' | 'email' | 'phone'
}

export const MEMBER_STATUS: Record<string, string> = {
  sent: 'ожидает', viewed: 'ожидает', conditionally_accepted: 'условное согласие', declined: 'отказ', expired: 'истекло',
  offer_v2: 'личное приглашение', accepted: 'принят', withdrawn: 'отозвано', countered: 'ожидает', revoked: 'контакты скрыты', company_declined: 'отклонено',
}

export const getGroupLimits = () => api<{ ttl_days: number; min_team: number }>('/employer/groups/limits')
export const createGroup = (body: GroupInput) => api<Group>('/employer/groups', { method: 'POST', body })
export const getGroups = () => api<GroupListItem[]>('/employer/groups')
export const getGroup = (id: string) => api<Group>(`/employer/groups/${id}`)
export const finalizeGroup = (id: string) => api<Group>(`/employer/groups/${id}/finalize`, { method: 'POST' })
export const withdrawGroup = (id: string) => api<Group>(`/employer/groups/${id}/withdraw`, { method: 'POST' })
export const conditionalAccept = (contactId: string) => api(`/candidate/invitations/${contactId}/conditional-accept`, { method: 'POST' })
export const conditionalWithdraw = (contactId: string) => api(`/candidate/invitations/${contactId}/conditional-withdraw`, { method: 'POST' })
