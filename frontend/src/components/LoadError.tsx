import { errorText } from '../api/errors'

/** Список не загрузился: пустая страница без объяснения выглядит как «данных нет». */
export default function LoadError({ error }: { error: unknown }) {
  return <p role="alert" className="text-sm text-danger">{errorText(error, 'Не удалось загрузить данные')}</p>
}
