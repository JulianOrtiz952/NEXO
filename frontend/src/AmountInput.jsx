import { useEffect, useRef } from 'react'
import { formatAmountInput } from './numberFormat.js'

export default function AmountInput({ name, labelId, defaultValue }) {
  const input = useRef(null)
  useEffect(() => {
    const element = input.current
    const reset = () => element.setCustomValidity('')
    const form = element.form
    form?.addEventListener('reset', reset)
    return () => form?.removeEventListener('reset', reset)
  }, [])

  function change(event) {
    const element = event.currentTarget
    if (!element.value) { element.setCustomValidity(''); return }
    const formatted = formatAmountInput(element.value)
    if (formatted === null) {
      element.setCustomValidity('Ingresa hasta 10 dígitos enteros y dos decimales con punto. Ejemplo: 11,999.85.')
      return
    }
    const count = element.value.slice(0, element.selectionStart).replace(/[,'’]/g, '').length
    element.value = formatted
    let position = 0
    let seen = 0
    while (position < formatted.length && seen < count) {
      if (!/[,'’]/.test(formatted[position])) seen += 1
      position += 1
    }
    element.setSelectionRange(position, position)
    element.setCustomValidity('')
  }

  return <input ref={input} name={name} defaultValue={defaultValue === undefined ? undefined : formatAmountInput(defaultValue)} type="text" inputMode="decimal" required aria-describedby={labelId}
    autoComplete="off" spellCheck={false} onChange={change} onKeyDown={event => {
      // RF-024: deleting next to a separator also deletes the adjacent digit.
      const element = event.currentTarget
      const start = element.selectionStart
      if (start !== element.selectionEnd) return
      if (event.key === 'Backspace' && /[,'’]/.test(element.value[start - 1] || '')) element.setSelectionRange(Math.max(0, start - 2), start)
      if (event.key === 'Delete' && /[,'’]/.test(element.value[start] || '')) element.setSelectionRange(start, start + 2)
    }} />
}
