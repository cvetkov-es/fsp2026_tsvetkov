import { ApiError } from './client'

/** Текст ошибки для человека: заголовок ответа сервера и, если есть, подробность («Ошибка проверки: Срок задачи истёк»). */
export const errorText = (e: unknown, fallback = 'Ошибка') =>
  e instanceof ApiError ? `${e.title}${e.detail ? `: ${e.detail}` : ''}` : fallback
