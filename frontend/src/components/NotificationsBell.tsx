import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getNotifications, readNotifications } from '../api/contacts'
import { BellIcon } from './icons'
import { useEscape } from './use-escape'

export function NotificationsBell() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['notifications'], queryFn: getNotifications, refetchInterval: 30_000 })
  const [open, setOpen] = useState(false)
  const unread = q.data?.unread ?? 0
  useEscape(open, () => setOpen(false))
  return (
    <div className="relative">
      <button type="button" aria-label={`Уведомления: ${unread} непрочитанных`} aria-haspopup="true" aria-expanded={open}
        className="relative grid size-9 place-items-center rounded-[10px] border border-line bg-white text-ink hover:bg-canvas"
        onClick={async () => {
          setOpen((v) => !v)
          if (!open && unread) { await readNotifications(); await qc.invalidateQueries({ queryKey: ['notifications'] }) }
        }}>
        <BellIcon />
        {unread > 0 && <span className="absolute -right-1.5 -top-1.5 min-w-[18px] rounded-full border-2 border-white bg-danger px-1 text-center text-[10px] font-semibold leading-[14px] text-white">{unread}</span>}
      </button>
      {open && (
        <>
          <button type="button" aria-hidden="true" tabIndex={-1} className="fixed inset-0 z-10 cursor-default" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-line bg-white p-2 text-ink shadow-lg">
            {q.data?.items.length ? q.data.items.map((n) => (
              <div key={n.id} className="rounded-lg px-3 py-2 text-sm hover:bg-canvas">
                {n.link ? <Link to={n.link} className="text-ink hover:text-primary" onClick={() => setOpen(false)}>{n.title}</Link> : n.title}
              </div>
            )) : <p className="px-3 py-2 text-sm text-muted">Уведомлений пока нет</p>}
          </div>
        </>
      )}
    </div>
  )
}
