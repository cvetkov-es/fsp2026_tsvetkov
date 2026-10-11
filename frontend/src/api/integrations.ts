import { api } from './client'

export type WebhookEndpoint = { id: string; url: string; created_at: string }
export type Delivery = {
  id: number; endpoint_id: string; event_type: string; at: string; status: 'pending' | 'delivered' | 'failed'
  status_code: number | null; attempt: number; error: string | null
}
export type Integrations = { endpoints: WebhookEndpoint[]; deliveries: Delivery[]; mock_available: boolean }
export type CreatedWebhook = { id: string; url: string; secret: string; page?: string | null }

export const DELIVERY_STATUS: Record<Delivery['status'], string> = { pending: 'ждёт отправки', delivered: 'доставлено', failed: 'не доставлено' }

export const getIntegrations = () => api<Integrations>('/employer/integrations')
export const createWebhook = (url: string) => api<CreatedWebhook>('/employer/integrations/webhooks', { method: 'POST', body: { url } })
export const connectMockAts = () => api<CreatedWebhook>('/employer/integrations/mock-ats', { method: 'POST' })
export const pingWebhook = (id: string) => api<{ queued: boolean }>(`/employer/integrations/webhooks/${id}/test`, { method: 'POST' })
export const deleteWebhook = (id: string) => api<void>(`/employer/integrations/webhooks/${id}`, { method: 'DELETE' })
