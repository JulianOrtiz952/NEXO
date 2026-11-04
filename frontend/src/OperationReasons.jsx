import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'
import { formatQuantity } from './numberFormat.js'

export default function OperationReasons({ onAccessError, refreshKey }) {
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('')
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [drafts, setDrafts] = useState({})
  const access = useRef(onAccessError)
  useEffect(() => { access.current = onAccessError }, [onAccessError])
  useEffect(() => {
    const controller = new AbortController()
    api('operation-reasons/', { signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) setData(result)
    }).catch(problem => {
      if (controller.signal.aborted) return
      setData(null); setError(problem.message)
      if ([401, 403].includes(problem.status)) access.current(problem)
    })
    return () => controller.abort()
  }, [refreshKey, version])

  async function save(event, row) {
    event.preventDefault()
    const form = event.currentTarget
    const payload = Object.fromEntries(new FormData(form))
    setBusy(true); setError(''); setMessage('')
    try {
      await api(row ? `operation-reasons/${row.id}/` : 'operation-reasons/', {
        method: row ? 'PATCH' : 'POST', body: JSON.stringify(payload),
      })
      if (!row) form.reset()
      else setDrafts(current => { const next = { ...current }; delete next[row.id]; return next })
      setMessage(row ? 'Motivo actualizado correctamente.' : 'Motivo creado correctamente.')
      setVersion(value => value + 1)
    } catch (problem) {
      setError(problem.message)
      if ([401, 403].includes(problem.status)) access.current(problem)
    } finally { setBusy(false) }
  }

  const rows = data?.results.filter(row => !filter || row.operation_type === filter)
  return <div className="zones-layout">
    <section className="identity-card"><p className="identity-eyebrow">MOTIVOS DEL RESTAURANTE</p><h2>Crear motivo</h2>
      <p className="identity-hint">Organiza los motivos según la operación a la que pertenecen.</p>
      <form className="identity-form" onSubmit={event => save(event)}><fieldset disabled={busy || !data}>
        <label>Nombre del motivo<input name="name" required maxLength={100} placeholder="Por ejemplo, Solicitud del cliente" /></label>
        <label>Tipo de operación<select name="operation_type" required defaultValue=""><option value="" disabled>Selecciona una operación</option>{data?.operation_types.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
        <button className="identity-primary" type="submit">Crear motivo →</button>
      </fieldset></form>
    </section>
    <section className="identity-card identity-directory"><div className="identity-directory-heading"><h2>Tus motivos</h2>{rows && <span className="identity-count">{formatQuantity(rows.length)} motivos</span>}</div>
      {message && <p role="status" className="identity-message">{message}</p>}
      {error && <div role="alert"><p className="identity-message">{error}</p><button className="identity-secondary" onClick={() => { setError(''); setVersion(value => value + 1) }}>Reintentar consulta</button></div>}
      <div className="identity-history-filter"><label>Filtrar por operación<select value={filter} onChange={event => setFilter(event.target.value)}><option value="">Todas las operaciones</option>{data?.operation_types.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label></div>
      {!data ? !error && <p role="status" className="identity-hint">Cargando motivos…</p> : !rows.length ? <p className="identity-empty">No hay motivos para esta selección.</p> : <ul className="identity-list">{rows.map(row => <li key={row.id}>
        <div className="identity-row-heading"><h3>{row.name}</h3><span className="identity-badge">{row.operation_type_label}</span></div>
        <form className="identity-form table-name-form" aria-label={`Editar motivo ${row.name}`} onSubmit={event => save(event, row)}><fieldset disabled={busy}>
          <label>Nombre de {row.name}<input name="name" required maxLength={100} value={drafts[row.id]?.name ?? row.name} onChange={event => setDrafts(current => ({ ...current, [row.id]: { ...current[row.id], name: event.target.value } }))} /></label>
          <label>Operación de {row.name}<select name="operation_type" value={drafts[row.id]?.operation_type ?? row.operation_type} onChange={event => setDrafts(current => ({ ...current, [row.id]: { ...current[row.id], operation_type: event.target.value } }))}>{data.operation_types.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
          <button className="identity-secondary" type="submit">Guardar motivo</button>
        </fieldset></form>
      </li>)}</ul>}
    </section>
  </div>
}
