import { api } from './client'
import type { Company } from './employer'

export const verifyDomain = () => api<Company>('/employer/company/verify-domain', { method: 'POST' })
export const verifyInn = (inn: string) => api<Company>('/employer/company/verify-inn', { method: 'POST', body: { inn } })
export const requestL3 = (comment: string) => api<Company>('/employer/company/l3-request', { method: 'POST', body: { comment } })
