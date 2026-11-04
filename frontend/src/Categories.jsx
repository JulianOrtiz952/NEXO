import { formatQuantity } from './numberFormat.js'
import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'
import RecordActions from './RecordActions.jsx'

// RF-023: live management scoped by the authenticated restaurant in the backend.
export default function Categories({ refreshKey, onAccessError }) {
  const [rows, setRows] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  const [pending, setPending] = useState(null)
  const [drafts, setDrafts] = useState({})
  const [editing, setEditing] = useState(null)
  const editTrigger = useRef(null)
  const accessError = useRef(onAccessError)
  useEffect(() => { accessError.current = onAccessError }, [onAccessError])
  const revision = useRef(0)
  const returnFocus = useRef(null)
  useEffect(() => {
    const current = ++revision.current
    api('categories/').then(data => { if (current === revision.current) { setRows(data); setError('') } }).catch(problem => {
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
      else {
        setDrafts(current => { const next = { ...current }; delete next[row.id]; return next })
        setEditing(null)
        editTrigger.current?.focus()
      }
    })
  }
  async function mutate(row, payload, success) {
    const current = revision.current
    setBusy(true); setMessage(''); setError('')
    try {
      await api(row ? `categories/${row.id}/` : 'categories/', { method: row ? 'PATCH' : 'POST', body: JSON.stringify(payload) })
      if (current !== revision.current) return
      success?.()
      setMessage(row ? 'Categoría actualizada correctamente.' : 'Categoría creada correctamente.')
      setVersion(value => value + 1)
    } catch (problem) {
      if (current === revision.current) {
        setError(problem.message)
        if ([401, 403].includes(problem.status)) accessError.current(problem)
      }
    } finally { setBusy(false) }
  }
  async function move(row, direction) {
    const ids = rows.map(item => item.id)
    const next = [...ids]
    const index = ids.indexOf(row.id)
    next[index] = ids[index + direction]
    next[index + direction] = row.id
    setBusy(true); setMessage(''); setError('')
    try {
      const updated = await api('categories/reorder/', { method: 'POST', body: JSON.stringify({ order: next, expected_order: ids }) })
      setRows(updated); setMessage('Orden de categorías actualizado.')
    } catch (problem) {
      setError(problem.message)
      if ([401, 403].includes(problem.status)) accessError.current(problem)
      if ([400, 409].includes(problem.status)) setVersion(value => value + 1)
    } finally { setBusy(false) }
  }
  function closeConfirmation() {
    setPending(null)
    returnFocus.current?.focus()
  }
  return <div className="zones-layout">
    <section className="identity-card"><p className="identity-eyebrow">ORGANIZA TU CARTA</p><h2>Crear categoría</h2><p className="identity-hint">Agrupa tus productos y define el orden de las categorías.</p>
      <form className="identity-form" onSubmit={event => save(event)}><fieldset disabled={busy}><label>Nombre de la categoría<input name="name" required maxLength={100} placeholder="Por ejemplo, Bebidas" autoComplete="off" /></label><small>Debe ser único en tu restaurante. Se creará activa y al final de la lista.</small><button className="identity-primary" type="submit">{busy ? 'Guardando…' : 'Crear categoría →'}</button></fieldset></form>
    </section>
    <section className="identity-card identity-directory"><div className="identity-directory-heading"><div><p className="identity-eyebrow">CATEGORÍAS DEL RESTAURANTE</p><h2>Tus categorías</h2></div>{rows && <span className="identity-count">{formatQuantity(rows.length)} categorías</span>}</div>
      {message && <p className="identity-message" role="status">{message}</p>}{error && <div role="alert"><p className="identity-message">{error}</p><button className="identity-secondary" onClick={() => setVersion(value => value + 1)}>Reintentar consulta</button></div>}
      {!rows ? !error && <p className="identity-hint" role="status">Cargando categorías…</p> : !rows.length ? <p className="identity-empty">Aún no tienes categorías. Crea la primera para organizar tu carta.</p> : <ul className="identity-list">{rows.map((row, index) => <li key={row.id}>
        <div className="identity-row-heading"><h3><span className="category-position">{formatQuantity(index + 1)}</span> {row.name}</h3><span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activa' : 'Inactiva'}</span></div>
        <RecordActions label={`Acciones de la categoría ${row.name}`} actions={[
          { id: 'edit', icon: 'edit', label: `Editar categoría ${row.name}`, hint: 'Editar nombre', disabled: busy, expanded: editing === row.id, onClick: event => { editTrigger.current = event.currentTarget; setEditing(current => current === row.id ? null : row.id) } },
          { id: 'up', icon: 'up', label: `Subir ${row.name}`, hint: 'Subir categoría', disabled: busy || index === 0, onClick: () => move(row, -1) },
          { id: 'down', icon: 'down', label: `Bajar ${row.name}`, hint: 'Bajar categoría', disabled: busy || index === rows.length - 1, onClick: () => move(row, 1) },
          { id: 'status', icon: 'status', label: `${row.is_active ? 'Desactivar' : 'Activar'} categoría ${row.name}`, hint: `${row.is_active ? 'Desactivar' : 'Activar'} categoría`, disabled: busy, onClick: event => {
            if (row.is_active) { returnFocus.current = event.currentTarget; setPending(row) }
            else mutate(row, { is_active: true })
          } },
        ]} />
        {editing === row.id && <form className="identity-update identity-role-update record-editor" aria-label={`Editar nombre de categoría ${row.name}`} onSubmit={event => save(event, row)}><fieldset disabled={busy}><label>Nombre de {row.name}<input autoFocus name="name" required maxLength={100} value={drafts[row.id] ?? row.name} onChange={event => setDrafts(current => ({ ...current, [row.id]: event.target.value }))} /></label><button className="identity-secondary" type="submit">Guardar nombre</button><button className="identity-secondary" type="button" onClick={() => { setEditing(null); setDrafts(current => { const next = { ...current }; delete next[row.id]; return next }); editTrigger.current?.focus() }}>Cancelar edición</button></fieldset></form>}
      </li>)}</ul>}
    </section>
    {pending && <div className="identity-confirm-overlay"><section className="identity-card identity-confirm" role="dialog" aria-modal="true" aria-labelledby="category-confirm-title" aria-describedby="category-confirm-description" onKeyDown={event => {
      if (event.key === 'Escape') closeConfirmation()
      if (event.key === 'Tab') {
        const buttons = event.currentTarget.querySelectorAll('button')
        if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[1].focus() }
        else if (!event.shiftKey && document.activeElement === buttons[1]) { event.preventDefault(); buttons[0].focus() }
      }
    }}><h2 id="category-confirm-title">Desactivar categoría</h2><p id="category-confirm-description" className="identity-hint">¿Quieres desactivar {pending.name}? Su registro y su historial se conservarán. Podrás reactivarla después.</p><div className="identity-status-control"><button className="identity-secondary" autoFocus onClick={closeConfirmation}>Cancelar</button><button className="identity-primary" onClick={() => { const row = pending; closeConfirmation(); mutate(row, { is_active: false }) }}>Confirmar desactivación</button></div></section></div>}
  </div>
}
