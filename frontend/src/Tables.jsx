import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'

// RF-013: configuration only; operational labels and states belong to later DNs.
export default function Tables({ refreshKey, onAccessError }) {
  const [zones, setZones] = useState(null)
  const [selection, setSelection] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  const accessError = useRef(onAccessError)
  const submitting = useRef(false)
  const mounted = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { accessError.current = onAccessError }, [onAccessError])
  const zone = zones?.find(item => item.id === selection) || zones?.find(item => item.is_active) || zones?.[0]
  const zoneId = zone?.id || ''
  const requestKey = `${zoneId}-${refreshKey}-${version}`
  const tables = result?.key === requestKey ? result.rows : null
  const listError = result?.key === requestKey ? result.error : ''
  useEffect(() => {
    let cancelled = false
    api('zones/').then(data => { if (!cancelled) { setZones(data); setError('') } }).catch(problem => {
      if (!cancelled) { setZones(null); setError(problem.message); if ([401, 403].includes(problem.status)) accessError.current(problem) }
    })
    return () => { cancelled = true }
  }, [refreshKey, version])
  useEffect(() => {
    if (!zoneId) return
    let cancelled = false
    api(`zones/${zoneId}/tables/`).then(rows => { if (!cancelled) setResult({ key: requestKey, rows }) }).catch(problem => {
      if (!cancelled) { setResult({ key: requestKey, error: problem.message }); if ([401, 403].includes(problem.status)) accessError.current(problem) }
    })
    return () => { cancelled = true }
  }, [zoneId, requestKey])
  async function create(event) {
    event.preventDefault()
    if (submitting.current || !zone?.is_active) return
    submitting.current = true
    setBusy(true); setError(''); setMessage('')
    try {
      await api(`zones/${zone.id}/tables/`, { method: 'POST', body: JSON.stringify({}) })
      if (!mounted.current) return
      setMessage(`Mesa creada en ${zone.name}.`)
      setVersion(value => value + 1)
    } catch (problem) {
      if (mounted.current) {
        setError(problem.message)
        if ([401, 403].includes(problem.status)) accessError.current(problem)
      }
    } finally { submitting.current = false; if (mounted.current) setBusy(false) }
  }
  return <section className="identity-card identity-directory">
    <div className="identity-directory-heading"><div><p className="identity-eyebrow">CONFIGURACIÓN POR ZONA</p><h2>Mesas del restaurante</h2></div>{tables && <span className="identity-count">{tables.length} {tables.length === 1 ? 'mesa' : 'mesas'}</span>}</div>
    <p className="identity-hint">Selecciona una zona para consultar sus mesas o crear una nueva.</p>
    {(error || listError) && <div role="alert"><p className="identity-message">{error || listError}</p><button className="identity-secondary" onClick={() => setVersion(value => value + 1)}>Reintentar consulta</button></div>}
    {message && <p className="identity-message" role="status">{message}</p>}
    {!zones ? !error && <p className="identity-hint" role="status">Cargando zonas…</p> : !zones.length ? <div className="identity-empty"><p>Primero crea una zona para ubicar las mesas de tu restaurante.</p><a className="identity-secondary" href="#zones">Ir a Zonas</a></div> : <>
      <form className="identity-form table-create-form" onSubmit={create}><fieldset disabled={busy}><label>Zona de las mesas<select value={zoneId} onChange={event => { setSelection(event.target.value); setMessage(''); setError('') }}>{zones.map(item => <option value={item.id} key={item.id}>{item.name}{item.is_active ? '' : ' · Inactiva'}</option>)}</select></label><button className="identity-primary" disabled={!zone?.is_active || !tables} type="submit">{busy ? 'Creando mesa…' : 'Crear mesa en esta zona →'}</button></fieldset></form>
      {!zone?.is_active && <p className="identity-message">Esta zona está inactiva. Sus mesas se conservan; actívala desde <a href="#zones">Zonas</a> antes de crear otras.</p>}
      <h3 className="table-zone-heading">{zone?.name}</h3>
      {!tables ? !listError && <p className="identity-hint" role="status">Cargando mesas…</p> : !tables.length ? <p className="identity-empty">Esta zona todavía no tiene mesas.</p> : <ul className="table-registration-list">{tables.map(table => <li key={table.id}><span className="table-registration-icon" aria-hidden="true">▦</span><div><h4>Mesa registrada</h4><p>Zona: {table.zone_name}</p><p>Creada el <time dateTime={table.created_at}>{new Date(table.created_at).toLocaleString('es-CO', { timeZone: 'America/Bogota' })}</time></p></div></li>)}</ul>}
    </>}
  </section>
}
