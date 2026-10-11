import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { errorText } from '../../api/errors'
import {
  connectMockAts, createWebhook, DELIVERY_STATUS, deleteWebhook, getIntegrations, pingWebhook, type CreatedWebhook,
} from '../../api/integrations'
import LoadError from '../LoadError'
import { Button, Input } from '../ui'

const when = (iso: string) => new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

/** Интеграции (ATS, процесс 4.7): вебхуки по Standard Webhooks; в событиях только псевдонимы и ссылка на контакт, без ПДн. */
export default function IntegrationsBlock() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['integrations'], queryFn: getIntegrations })
  const [url, setUrl] = useState('')
  const [created, setCreated] = useState<CreatedWebhook | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const reload = () => qc.invalidateQueries({ queryKey: ['integrations'] })
  const run = async (f: () => Promise<void>) => {
    setError(null)
    setNote(null)
    setBusy(true)
    try { await f(); await reload() } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
  }
  const d = q.data
  return (
    <div className="mt-6 space-y-3 border-t border-line pt-4">
      <h2 className="text-lg font-semibold">Интеграции (ATS)</h2>
      <p className="text-sm text-muted">Отправляем события по приглашениям и этапам найма на ваш адрес: подписанные вебхуки по Standard Webhooks. В событии есть псевдоним кандидата и ссылки, без ФИО и контактов.</p>
      {q.isError && <LoadError error={q.error} />}
      {q.isLoading && <p className="text-sm text-muted">Загрузка…</p>}
      {d && d.endpoints.length === 0 && <p className="text-sm text-muted">Вебхуков пока нет.</p>}
      <ul className="space-y-2 text-sm">{d?.endpoints.map((e) => (
        <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-2">
          <span className="break-all font-mono text-xs">{e.url}</span>
          <span className="flex gap-3">
            <button className="text-primary hover:underline" disabled={busy} onClick={() => void run(async () => { await pingWebhook(e.id); setNote('Проверочное событие уйдёт в течение минуты') })}>Проверить (ping)</button>
            <button className="text-danger hover:underline" disabled={busy} onClick={() => void run(async () => { await deleteWebhook(e.id) })}>Отключить</button>
          </span>
        </li>
      ))}</ul>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm">Адрес (https)
          <div className="w-80 max-w-full"><Input aria-label="Адрес (https)" type="url" value={url} onChange={(e) => setUrl(e.target.value)} /></div></label>
        <Button type="button" disabled={busy || url.trim().length < 8} onClick={() => void run(async () => { setCreated(await createWebhook(url.trim())); setUrl('') })}>Добавить вебхук</Button>
        {d?.mock_available && <button className="text-sm text-primary hover:underline" disabled={busy} onClick={() => void run(async () => { setCreated(await connectMockAts()) })}>Подключить демо-ATS</button>}
      </div>
      {created && (
        <div className="rounded-xl bg-surface-2 p-3 text-sm">
          <p className="font-semibold">Сохраните секрет: он больше не покажется</p>
          <code className="mt-1 block break-all rounded bg-white p-2 font-mono text-xs">{created.secret}</code>
          {created.page && <a className="mt-2 inline-block text-primary hover:underline" href={created.page} target="_blank" rel="noreferrer">Страница демо-ATS</a>}
          <button className="ml-4 text-primary hover:underline" onClick={() => setCreated(null)}>Секрет сохранён</button>
        </div>
      )}
      {note && <p className="text-sm text-muted">{note}</p>}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {d && d.deliveries.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Журнал доставок</h3>
          <ul className="space-y-1 text-xs">{d.deliveries.map((x) => (
            <li key={x.id}>{`${x.event_type} · ${when(x.at)} · ${DELIVERY_STATUS[x.status]}${x.status_code ? ` · код ${x.status_code}` : ''}${x.attempt ? ` · попытка ${x.attempt}` : ''}`}</li>
          ))}</ul>
        </div>
      )}
    </div>
  )
}
