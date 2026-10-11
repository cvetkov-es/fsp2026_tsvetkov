import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { getContact, getMessages, postMessage, STATUS_TITLE } from '../api/contacts'
import { Chat } from '../components/Chat'
import { Card, Page } from '../components/ui'

export default function ContactPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  // Контакты (с записью просмотра в аудит) грузятся один раз; опрашивается только переписка
  const q = useQuery({ queryKey: ['contact', id], queryFn: () => getContact(id) })
  const chat = useQuery({ queryKey: ['contact-messages', id], queryFn: () => getMessages(id), refetchInterval: 15_000 })
  const c = q.data
  if (!c) return <Page narrow><p>Загрузка…</p></Page>
  return (
    <Page narrow>
      <Card className="space-y-2">
        <p className="text-sm text-muted">{c.need_title} · {STATUS_TITLE[c.status]}</p>
        {c.role === 'employer' ? (
          <>
            <h1 className="text-3xl font-semibold tracking-[-0.03em]">{c.candidate?.full_name ?? c.alias}</h1>
            {c.candidate ? (
              <ul className="mt-2 text-sm">
                <li>Email: {c.candidate.email}</li>
                {Object.entries(c.candidate.contacts).map(([k, v]) => <li key={k}>{k}: {v}</li>)}
              </ul>
            ) : <p className="mt-2 text-sm text-muted">Контакты откроются, когда кандидат примет приглашение.</p>}
          </>
        ) : (
          <>
            <h1 className="text-3xl font-semibold tracking-[-0.03em]">{c.company.name}</h1>
            <p className="text-sm">{c.company.industry} · уровень доверия {c.company.trust_level}</p>
            {c.company.description && <p className="mt-2 text-sm">{c.company.description}</p>}
          </>
        )}
      </Card>
      <Card>
        <h2 className="mb-4 text-lg font-semibold">Чат</h2>
        <Chat messages={chat.data ?? c.messages} open={c.chat_open} onSend={async (text) => { await postMessage(id, text); await qc.invalidateQueries({ queryKey: ['contact-messages', id] }) }} />
      </Card>
    </Page>
  )
}
