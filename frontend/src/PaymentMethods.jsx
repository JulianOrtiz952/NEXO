import { formatQuantity } from './numberFormat.js'
import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'

// RF-020: live management scoped by the authenticated restaurant in the backend.
export default function PaymentMethods({ refreshKey, onAccessError }) {
  const [rows, setRows] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  const [pending, setPending] = useState(null)
  const [drafts, setDrafts] = useState({})
  const accessError = useRef(onAccessError)
  useEffect(() => { accessError.current = onAccessError }, [onAccessError])
  const revision = useRef(0)
  const returnFocus = useRef(null)
  useEffect(() => {
    const current = ++revision.current
    api('payment-methods/').then(data => { if (current === revision.current) { setRows(data); setError('') } }).catch(problem => {
      if (current === revision.current) { setRows(null); setError(problem.message); if ([401, 403].includes(problem.status)) accessError.current(problem) }
    })
    return () => { revision.current += 1 }
  }, [refreshKey, version])
  async function save(event, row) {
    event.preventDefault()
    const form = event.currentTarget
    const name = new FormData(form).get('name')
    await mutate(row, { name }, () => {
      if (!row) form.reset()
      else setDrafts(current => { const next = { ...current }; delete next[row.id]; return next })
    })
  }
  async function mutate(row, payload, success) {
    const current = revision.current
    setBusy(true); setMessage(''); setError('')
    try {
      await api(row ? `payment-methods/${row.id}/` : 'payment-methods/', { method: row ? 'PATCH' : 'POST', body: JSON.stringify(payload) })
      if (current !== revision.current) return
      success?.()
      setMessage(row ? 'Método de pago actualizado correctamente.' : 'Método de pago creado correctamente.')
      setVersion(value => value + 1)
    } catch (problem) {
      if (current === revision.current) {
        setError(problem.message)
        if ([401, 403].includes(problem.status)) accessError.current(problem)
      }
    } finally { setBusy(false) }
  }
  function closeConfirmation() {
    setPending(null)
    returnFocus.current?.focus()
  }
  return <div className="zones-layout">
    <section className="identity-card"><p className="identity-eyebrow">CONFIGURACIÓN DE COBROS</p><h2>Crear método de pago</h2><p className="identity-hint">Configura los métodos de pago de tu restaurante.</p>
      <form className="identity-form" onSubmit={event => save(event)}><fieldset disabled={busy}><label>Nombre del método de pago<input name="name" required maxLength={100} placeholder="Por ejemplo, Efectivo" autoComplete="off" /></label><small>El método de pago se creará activo.</small><button className="identity-primary" type="submit">{busy ? 'Guardando…' : 'Crear método de pago →'}</button></fieldset></form>
    </section>
    <section className="identity-card identity-directory"><div className="identity-directory-heading"><div><p className="identity-eyebrow">MÉTODOS DEL RESTAURANTE</p><h2>Tus métodos de pago</h2></div>{rows && <span className="identity-count">{formatQuantity(rows.length)} métodos de pago</span>}</div>
      {message && <p className="identity-message" role="status">{message}</p>}{error && <div role="alert"><p className="identity-message">{error}</p><button className="identity-secondary" onClick={() => setVersion(value => value + 1)}>Reintentar consulta</button></div>}
      {!rows ? !error && <p className="identity-hint" role="status">Cargando métodos de pago…</p> : !rows.length ? <p className="identity-empty">Aún no tienes métodos de pago. Crea el primero para configurar los cobros.</p> : <ul className="identity-list">{rows.map(row => <li key={row.id}>
        <div className="identity-row-heading"><h3>{row.name}</h3><span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span></div>
        <form className="identity-update identity-role-update" aria-label={`Editar método de pago ${row.name}`} onSubmit={event => save(event, row)}><fieldset disabled={busy}><label>Nombre de {row.name}<input name="name" required maxLength={100} value={drafts[row.id] ?? row.name} onChange={event => setDrafts(current => ({ ...current, [row.id]: event.target.value }))} /></label><button className="identity-secondary" type="submit">Guardar nombre</button></fieldset></form>
        <div className="identity-status-control"><button className="identity-secondary" disabled={busy} onClick={event => {
          if (row.is_active) { returnFocus.current = event.currentTarget; setPending(row) }
          else mutate(row, { is_active: true })
        }}>{row.is_active ? 'Desactivar método de pago' : 'Activar método de pago'}</button></div>
      </li>)}</ul>}
    </section>
    {pending && <div className="identity-confirm-overlay"><section className="identity-card identity-confirm" role="dialog" aria-modal="true" aria-labelledby="payment-confirm-title" aria-describedby="payment-confirm-description" onKeyDown={event => {
      if (event.key === 'Escape') closeConfirmation()
      if (event.key === 'Tab') {
        const buttons = event.currentTarget.querySelectorAll('button')
        if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[1].focus() }
        else if (!event.shiftKey && document.activeElement === buttons[1]) { event.preventDefault(); buttons[0].focus() }
      }
    }}><h2 id="payment-confirm-title">Desactivar método de pago</h2><p id="payment-confirm-description" className="identity-hint">¿Quieres desactivar {pending.name}? Su registro y su historial se conservarán. Podrás reactivarlo después.</p><div className="identity-status-control"><button className="identity-secondary" autoFocus onClick={closeConfirmation}>Cancelar</button><button className="identity-primary" onClick={() => { const row = pending; closeConfirmation(); mutate(row, { is_active: false }) }}>Confirmar desactivación</button></div></section></div>}
  </div>
}
