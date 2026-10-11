import { useState } from 'react'
import type { ChatMessage } from '../api/contacts'
import { Button, Input } from './ui'

/** Минимальный тред сообщений внутри контакта (процесс 2.8). */
export function Chat({ messages, open, onSend }: { messages: ChatMessage[]; open: boolean; onSend: (text: string) => Promise<void> }) {
  const [text, setText] = useState('')
  return (
    <div className="space-y-3">
      <div className="max-h-96 space-y-2 overflow-y-auto">
        {messages.length === 0 && <p className="text-sm text-muted">Сообщений пока нет.</p>}
        {messages.map((m) => (
          <div key={m.id} className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm ${m.mine ? 'ml-auto bg-primary text-white' : 'bg-canvas text-ink'}`}>
            <p>{m.text}</p>
            <p className="mt-1 text-xs opacity-60">{m.author === 'company' ? 'Компания' : 'Кандидат'} · {new Date(m.at).toLocaleString('ru-RU')}</p>
          </div>
        ))}
      </div>
      {open ? (
        <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (!text.trim()) return; await onSend(text); setText('') }}>
          <label htmlFor="chat-input" className="sr-only">Сообщение</label>
          <Input id="chat-input" className="flex-1" value={text} onChange={(e) => setText(e.target.value)} placeholder="Сообщение" />
          <Button type="submit" disabled={!text.trim()}>Отправить</Button>
        </form>
      ) : <p className="text-sm text-muted">Чат открывается, когда приглашение принято, и закрывается, если кандидат скрыл контакты.</p>}
    </div>
  )
}
