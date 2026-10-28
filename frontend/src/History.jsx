import { useEffect, useState } from 'react'
import { api } from './identityApi.js'

const actions = { 'table.created': 'Mesa creada', 'user.created': 'Usuario creado', 'user.email_changed': 'Correo modificado', 'user.role_changed': 'Rol modificado', 'user.status_changed': 'Estado del usuario modificado', 'prospective_owner.created': 'Cuenta de Dueño creada', 'zone.created': 'Zona creada', 'zone.updated': 'Zona modificada', 'zone.status_changed': 'Estado de la zona modificado', 'restaurant.created': 'Restaurante creado', 'restaurant.owner_assigned': 'Dueño vinculado', 'restaurant.status_changed': 'Estado del restaurante modificado' }
const fields = { zone_name: 'Zona', email: 'Correo', role: 'Rol', is_active: 'Estado', name: 'Nombre', owner: 'Dueño vinculado', cascading: 'Afecta al acceso del restaurante' }
const roles = { OWNER: 'Dueño', ADMIN: 'Administrador', CASHIER: 'Caja', WAITER: 'Mesero', KITCHEN: 'Cocina' }
function describe(values) {
  return Object.entries(values).map(([key, value]) => `${fields[key] || key}: ${key === 'is_active' ? value ? 'Activo' : 'Inactivo' : key === 'cascading' ? value ? 'Sí' : 'No' : roles[value] || value}`).join(' · ') || 'Sin valor anterior'
}

export default function History({ refreshKey }) {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [retry, setRetry] = useState(0)
  const [action, setAction] = useState('')
  const [options, setOptions] = useState([])
  const requestKey = `${page}-${action}-${refreshKey}-${retry}`
  const data = result?.key === requestKey ? result.data : null
  const error = result?.key === requestKey ? result.error : ''
  useEffect(() => {
    let cancelled = false
    api(`history/?page=${page}&action=${encodeURIComponent(action)}`).then(data => { if (!cancelled) { setResult({ key: requestKey, data }); setOptions(data.action_options) } }).catch(problem => { if (!cancelled) setResult({ key: requestKey, error: problem.message }) })
    return () => { cancelled = true }
  }, [page, action, requestKey])
  return <section className="identity-card identity-directory" id="history">
    <div className="identity-directory-heading"><div><p className="identity-eyebrow">TRAZABILIDAD DEL RESTAURANTE</p><h2>Historial de cambios</h2></div><span className="identity-count">Solo lectura</span></div>
    <p className="identity-hint">Consulta los registros por tipo de acción. Cada cambio conserva su responsable y sus valores anteriores.</p>
    <div className="identity-history-filter"><label>Tipo de acción<select value={action} onChange={event => { setAction(event.target.value); setPage(1) }}><option value="">Todas las acciones</option>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>{action && <button className="identity-secondary" onClick={() => { setAction(''); setPage(1) }}>Limpiar filtro</button>}</div>
    {error ? <div role="alert"><p className="identity-message">{error}</p><button className="identity-secondary" onClick={() => setRetry(value => value + 1)}>Reintentar</button></div> : !data ? <p role="status" className="identity-hint">Cargando historial…</p> : <>
      {!data.results.length ? <p className="identity-empty">{action ? 'No hay registros para este tipo de acción.' : 'Todavía no hay acciones registradas.'}</p> : <ol className="identity-list">{data.results.map(event => <li key={event.id}>
        <p className="identity-event-type">{event.category} · {event.action_type}</p>
        <div className="identity-row-heading"><h3>{event.action === 'user.status_changed' && event.after.cascading ? event.after.is_active ? 'Acceso del restaurante reactivado' : 'Acceso del restaurante suspendido' : actions[event.action] || 'Cambio registrado'}</h3><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString('es-CO', { timeZone: 'America/Bogota' })}</time></div>
        <p className="identity-hint">{event.target} · {event.restaurant}<br />Realizado por: {event.actor}</p>
        <dl className="identity-history-values"><div><dt>Antes</dt><dd>{describe(event.before)}</dd></div><div><dt>Después</dt><dd>{describe(event.after)}</dd></div></dl>
      </li>)}</ol>}
      <div className="identity-history-pages"><button className="identity-secondary" disabled={!data.previous} onClick={() => setPage(value => value - 1)}>Más recientes</button><span>Página {page} · {data.count} acciones</span><button className="identity-secondary" disabled={!data.next} onClick={() => setPage(value => value + 1)}>Anteriores</button></div>
    </>}
  </section>
}
