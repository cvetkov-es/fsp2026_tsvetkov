import { createContext, useContext, useEffect } from 'react'

/** Фокус-режим теста: пока страница включена в него, шапка сайта недоступна ни мыши, ни клавиатуре, ни скринридеру. */
export const FocusModeContext = createContext<(on: boolean) => void>(() => {})

export function useFocusMode(active: boolean) {
  const set = useContext(FocusModeContext)
  useEffect(() => {
    set(active)
    return () => set(false)
  }, [active, set])
}
