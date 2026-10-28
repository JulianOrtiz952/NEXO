import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'

// RF-012: live management scoped by the authenticated restaurant in the backend.
export default function Zones({ refreshKey, onAccessError }) {
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
    api('zones/').then(data => { if (current === revision.current) { setRows(data); setError('') } }).catch(problem => {
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
      await api(row ? `zones/${row.id}/` : 'zones/', { method: row ? 'PATCH' : 'POST', body: JSON.stringify(payload) })
      if (current !== revision.current) return
      success?.()
      setMessage(row ? 'Zona actualizada correctamente.' : 'Zona creada correctamente.')
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
    <section className="identity-card"><p className="identity-eyebrow">ORGANIZA TU ESPACIO</p><h2>Crear zona</h2><p className="identity-hint">Agrupa los espacios de tu restaurante. Después podrás vincular sus mesas.</p>
      <form className="identity-form" onSubmit={event => save(event)}><fieldset disabled={busy}><label>Nombre de la zona<input name="name" required maxLength={100} placeholder="Por ejemplo, Terraza" autoComplete="off" /></label><small>Debe ser único en tu restaurante. La zona se creará activa.</small><button className="identity-primary" type="submit">{busy ? 'Guardando…' : 'Crear zona →'}</button></fieldset></form>
    </section>
    <section className="identity-card identity-directory"><div className="identity-directory-heading"><div><p className="identity-eyebrow">ESPACIOS DEL RESTAURANTE</p><h2>Tus zonas</h2></div>{rows && <span className="identity-count">{rows.length} zonas</span>}</div>
      {message && <p className="identity-message" role="status">{message}</p>}{error && <div role="alert"><p className="identity-message">{error}</p><button className="identity-secondary" onClick={() => setVersion(value => value + 1)}>Reintentar consulta</button></div>}
      {!rows ? !error && <p className="identity-hint" role="status">Cargando zonas…</p> : !rows.length ? <p className="identity-empty">Aún no tienes zonas. Crea la primera para organizar tu restaurante.</p> : <ul className="identity-list">{rows.map(row => <li key={row.id}>
        <div className="identity-row-heading"><h3>{row.name}</h3><span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activa' : 'Inactiva'}</span></div>
        <form className="identity-update identity-role-update" aria-label={`Editar zona ${row.name}`} onSubmit={event => save(event, row)}><fieldset disabled={busy}><label>Nombre de {row.name}<input name="name" required maxLength={100} value={drafts[row.id] ?? row.name} onChange={event => setDrafts(current => ({ ...current, [row.id]: event.target.value }))} /></label><button className="identity-secondary" type="submit">Guardar nombre</button></fieldset></form>
        <div className="identity-status-control"><button className="identity-secondary" disabled={busy} onClick={event => {
          if (row.is_active) { returnFocus.current = event.currentTarget; setPending(row) }
          else mutate(row, { is_active: true })
        }}>{row.is_active ? 'Desactivar zona' : 'Activar zona'}</button></div>
      </li>)}</ul>}
    </section>
    {pending && <div className="identity-confirm-overlay"><section className="identity-card identity-confirm" role="dialog" aria-modal="true" aria-labelledby="zone-confirm-title" aria-describedby="zone-confirm-description" onKeyDown={event => {
      if (event.key === 'Escape') closeConfirmation()
      if (event.key === 'Tab') {
        const buttons = event.currentTarget.querySelectorAll('button')
        if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[1].focus() }
        else if (!event.shiftKey && document.activeElement === buttons[1]) { event.preventDefault(); buttons[0].focus() }
      }
    }}><h2 id="zone-confirm-title">Desactivar zona</h2><p id="zone-confirm-description" className="identity-hint">¿Quieres desactivar {pending.name}? Su registro y su historial se conservarán. Podrás reactivarla después.</p><div className="identity-status-control"><button className="identity-secondary" autoFocus onClick={closeConfirmation}>Cancelar</button><button className="identity-primary" onClick={() => { const row = pending; closeConfirmation(); mutate(row, { is_active: false }) }}>Confirmar desactivación</button></div></section></div>}
  </div>
}
