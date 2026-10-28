import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'
import './Identity.css'
import History from './History.jsx'
import Zones from './Zones.jsx'
const labels = { users: 'Usuarios', tables: 'Mesas', kitchen: 'Cocina', menu: 'Carta', cashier: 'Caja', restaurants: 'Restaurantes' }
const roles = { OWNER: 'Dueño', ADMIN: 'Administrador', CASHIER: 'Caja', WAITER: 'Mesero', KITCHEN: 'Cocina' }

export default function Identity() {
  const [user, setUser] = useState(null)
  const [section, setSection] = useState(() => window.location.hash.slice(1))
  const [rows, setRows] = useState([])
  const [owners, setOwners] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [emailDrafts, setEmailDrafts] = useState({})
  const [historyVersion, setHistoryVersion] = useState(0)
  const [pendingStatus, setPendingStatus] = useState(null)
  const revision = useRef(0)
  function clearAccess(error) {
    revision.current += 1
    setUser(null)
    setRows([])
    setOwners([])
    setEmailDrafts({})
    setPendingStatus(null)
    setMessage(error.message)
    if (error.status === 401 || error.status === 403) sessionStorage.removeItem('nexo-token')
  }
  async function refresh() {
    const current = ++revision.current
    try {
      const profile = await api('auth/me/')
      if (current !== revision.current) return false
      setUser(profile)
      if (!profile.modules.includes('users')) setEmailDrafts({})
      if (!profile.modules.includes('users') && profile.role !== 'PLATFORM_ADMIN') setPendingStatus(null)
      setRows([])
      setOwners([])
      const path = profile.modules.includes('users') ? 'users/' : profile.modules.includes('restaurants') ? 'platform/restaurants/' : null
      const [updatedRows, candidates] = await Promise.all([path ? api(path) : [], profile.role === 'PLATFORM_ADMIN' ? api('platform/owners/') : []])
      if (current !== revision.current) return false
      setRows(updatedRows)
      setOwners(candidates)
      setHistoryVersion(value => value + 1)
      setMessage('')
      return true
    } catch (error) {
      if (current === revision.current) clearAccess(error)
      return false
    }
  }
  async function handleError(error) {
    if (error.status === 401) clearAccess(error)
    else if (error.status === 403) { await refresh(); setMessage(error.message) }
    else setMessage(error.message)
  }
  useEffect(() => {
    if (!sessionStorage.getItem('nexo-token')) { window.location.replace('/login'); return }
    const mountedRevision = revision.current
    queueMicrotask(() => { if (revision.current === mountedRevision) refresh() })
    const checkAccess = () => { if (sessionStorage.getItem('nexo-token')) refresh() }
    const timer = setInterval(checkAccess, 30000)
    window.addEventListener('focus', checkAccess)
    return () => { revision.current += 1; clearInterval(timer); window.removeEventListener('focus', checkAccess) }
  }, [])
  useEffect(() => {
    const changeSection = () => setSection(window.location.hash.slice(1))
    window.addEventListener('hashchange', changeSection)
    return () => window.removeEventListener('hashchange', changeSection)
  }, [])
  useEffect(() => { window.scrollTo(0, 0) }, [section])
  async function logout() {
    try { await api('auth/logout/', { method: 'POST' }) }
    catch (error) { await handleError(error); return }
    revision.current += 1
    setUser(null); setRows([]); setOwners([])
    setEmailDrafts({})
    sessionStorage.removeItem('nexo-token')
    window.location.assign('/login')
  }
  async function submit(event, kind) {
    event.preventDefault()
    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form))
    if (kind === 'restaurant') data.owner = Number(data.owner)
    const path = kind === 'restaurant' ? 'platform/restaurants/' : kind === 'owner' ? 'platform/owners/' : 'users/'
    setBusy(true); setMessage('')
    try {
      await api(path, { method: 'POST', body: JSON.stringify(data) })
      form.reset(); if (await refresh()) setMessage(kind === 'owner' ? 'Cuenta creada. Ya puedes seleccionarla al vincular un restaurante.' : 'Registro creado correctamente.')
    } catch (error) { await handleError(error) }
    finally { setBusy(false) }
  }
  async function updateRestaurant(event, id) {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget))
    const payload = { id, is_active: data.is_active === 'true' }
    if (data.owner) payload.owner = Number(data.owner)
    setBusy(true); setMessage('')
    try {
      await api('platform/restaurants/', { method: 'PATCH', body: JSON.stringify(payload) })
      if (await refresh()) setMessage('Restaurante actualizado.')
    } catch (error) { await handleError(error) }
    finally { setBusy(false) }
  }
  async function updateRole(event, id) {
    event.preventDefault()
    const role = new FormData(event.currentTarget).get('role')
    setBusy(true); setMessage('')
    try {
      await api('users/', { method: 'PATCH', body: JSON.stringify({ id, role }) })
      if (await refresh()) setMessage('Rol actualizado. Los permisos ya están vigentes.')
    } catch (error) { await handleError(error) }
    finally { setBusy(false) }
  }
  async function updateInitialOwnerRole(event, restaurant) {
    event.preventDefault()
    const role = new FormData(event.currentTarget).get('role')
    setBusy(true); setMessage('')
    try {
      await api('platform/initial-owner-role/', { method: 'PATCH', body: JSON.stringify({ restaurant, role }) })
      if (await refresh()) setMessage('Rol del primer Dueño actualizado. El restaurante conserva un Dueño activo.')
    } catch (error) { await handleError(error) }
    finally { setBusy(false) }
  }
  async function updateEmail(event, id) {
    event.preventDefault()
    const email = new FormData(event.currentTarget).get('email')
    setBusy(true); setMessage('')
    try {
      await api(`users/${id}/`, { method: 'PATCH', body: JSON.stringify({ email }) })
      setEmailDrafts(current => { const updated = { ...current }; delete updated[id]; return updated })
      if (await refresh()) setMessage('Correo actualizado. Usa el nuevo correo para el próximo inicio de sesión.')
    } catch (error) { await handleError(error) }
    finally { setBusy(false) }
  }
  async function updateStatus(target, active, platformStatus = false) {
    setPendingStatus(null)
    setBusy(true); setMessage('')
    try {
      const path = platformStatus ? 'platform/initial-owner-status/' : `users/${target.id}/status/`
      const payload = platformStatus ? { restaurant: target.id, is_active: active } : { is_active: active }
      await api(path, { method: 'PATCH', body: JSON.stringify(payload) })
      if (await refresh()) setMessage(active ? 'Acceso reactivado. Los usuarios desactivados individualmente siguen bloqueados.' : platformStatus ? 'Dueño inactivo: acceso del restaurante suspendido.' : 'Usuario desactivado. Su información histórica se conserva.')
    } catch (error) { await handleError(error) }
    finally { setBusy(false) }
  }
  if (!user) return <main className="identity-gate"><a className="welcome-logo" href="/">NEX<span>O</span></a><h1>Tu espacio en NEXO</h1><p role="status">{message || 'Validando tu acceso…'}</p><a className="identity-primary" href="/login">Iniciar sesión →</a></main>
  const platform = user.role === 'PLATFORM_ADMIN'
  const canManage = user.modules.includes('users')
  const availableSections = platform ? ['accounts', 'restaurants', 'history'] : canManage ? ['accounts', 'zones', 'history', 'access'] : ['access']
  const activeSection = availableSections.includes(section) ? section : availableSections[0]
  const sectionLabels = { accounts: platform ? 'Dueños' : 'Usuarios y roles', restaurants: 'Restaurantes', history: 'Historial', zones: 'Zonas', access: 'Mi acceso' }
  return <div className="identity-shell">
    <aside className="identity-sidebar">
      <a className="identity-brand" href="/">NEX<span>O</span></a><p className="identity-caption">CADA CONEXIÓN CUENTA</p>
      <p className="identity-section-label">TU ESPACIO</p>
      <nav aria-label="Gestión autorizada">
        {availableSections.map(item => <a key={item} href={`#${item}`} aria-current={activeSection === item ? 'page' : undefined}><span aria-hidden="true">{({ accounts: '◎', restaurants: '▦', history: '◷', zones: '▦', access: '◇' })[item]}</span><span>{sectionLabels[item]}</span></a>)}
      </nav>
      <div className="identity-side-note"><span>Una operación conectada.</span><p>{platform ? 'Cada restaurante, con su propio equipo y su propio espacio.' : 'Las personas correctas, en cada lugar de tu restaurante.'}</p></div>
      <div className="identity-profile"><span className="identity-avatar">{user.email.slice(0, 1).toUpperCase()}</span><div><strong>{roles[user.role] || 'Administrador global'}</strong><small>{user.email}</small></div></div>
      <button className="identity-logout" onClick={logout}>Cerrar sesión ↗</button>
    </aside>
    <main className="identity-main">
      <header className="identity-topbar"><span>NEXO / {platform ? 'Plataforma' : user.restaurant.name} / {sectionLabels[activeSection]}</span><span className="identity-session">Sesión de 1 hora</span></header>
      <div className="identity-content">
        <header className="identity-heading"><p className="identity-eyebrow">{platform ? 'ADMINISTRACIÓN DE PLATAFORMA' : 'TU RESTAURANTE, CONECTADO'}</p><h1>{activeSection === 'zones' ? 'Cada espacio, en su lugar.' : activeSection === 'history' ? 'Cada cambio, con su historia.' : activeSection === 'restaurants' ? 'Conecta cada restaurante.' : activeSection === 'access' ? 'Tu espacio en NEXO.' : platform ? 'Las personas detrás de cada espacio.' : 'Personas que hacen equipo.'}</h1><p>{activeSection === 'zones' ? 'Crea y organiza las zonas de tu restaurante.' : activeSection === 'history' ? 'Consulta quién realizó cada cambio, cuándo ocurrió y cuáles fueron sus valores anteriores y nuevos.' : activeSection === 'access' ? 'Estos son los módulos habilitados para tu rol y tu restaurante.' : platform ? activeSection === 'restaurants' ? 'Crea restaurantes, vincula Dueños y administra su acceso.' : 'Crea las cuentas de futuros Dueños para vincularlas después a un restaurante.' : `Administra los accesos de ${user.restaurant.name}. Cada persona, con el rol que necesita.`}</p></header>
        {activeSection !== 'history' && <div className="identity-summary"><div><span>{platform ? 'RESTAURANTES' : 'RESTAURANTE'}</span><strong>{platform ? rows.length : user.restaurant.name}</strong></div><div><span>{platform ? 'DUEÑOS POR VINCULAR' : 'TU ROL'}</span><strong>{platform ? owners.length : roles[user.role]}</strong></div><div><span>ACCESO</span><strong>{platform ? 'Administración global' : 'Solo tu restaurante'}</strong></div></div>}
        {message && <p className="identity-message" role="status">{message}</p>}
        {(platform || canManage) && ['accounts', 'restaurants'].includes(activeSection) && <div className="identity-grid">
          {activeSection === 'accounts' && <section className="identity-card" id="accounts"><div className="identity-card-heading"><span className="identity-step">{platform ? '01' : '◎'}</span><div><h2>{platform ? 'Crear cuenta del Dueño' : 'Crear usuario'}</h2><p>{platform ? 'La cuenta podrá ingresar cuando tenga un restaurante vinculado.' : 'El nuevo usuario pertenecerá a este restaurante.'}</p></div></div>
            <form className="identity-form" onSubmit={event => submit(event, platform ? 'owner' : 'user')}>
              <fieldset disabled={busy}><label>Correo electrónico<input name="email" required type="email" maxLength={150} autoComplete="off" placeholder="nombre@ejemplo.com" /></label><label>Contraseña inicial<input name="password" required type="password" autoComplete="new-password" placeholder="Crea una contraseña segura" /></label><small>Usa al menos 8 caracteres y evita contraseñas comunes o solo numéricas.</small>
                {!platform && <label>Rol del usuario<select name="role" defaultValue="WAITER">{Object.entries(roles).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
                <button className="identity-primary" type="submit">{busy ? 'Guardando…' : platform ? 'Crear cuenta del Dueño →' : 'Crear usuario →'}</button>
              </fieldset>
            </form>
          </section>}
          {platform && activeSection === 'restaurants' ? <section className="identity-card" id="new-restaurant"><div className="identity-card-heading"><span className="identity-step">02</span><div><h2>Vincular nuevo restaurante</h2><p>Selecciona el correo del Dueño que administrará este espacio.</p></div></div>
            <form className="identity-form" onSubmit={event => submit(event, 'restaurant')}><fieldset disabled={busy || !owners.length}><label>Nombre del restaurante<input name="name" required maxLength={160} placeholder="Nombre de tu restaurante" /></label><label>Dueño<select name="owner" required defaultValue=""><option value="" disabled>Selecciona un correo</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.email}</option>)}</select></label><button className="identity-primary" type="submit">Crear y vincular restaurante →</button></fieldset></form>
            {!owners.length && <p className="identity-hint">Primero crea una cuenta de Dueño. Solo aparecen cuentas activas sin restaurante.</p>}
          </section> : !platform ? <section className="identity-card"><p className="identity-eyebrow">ACCESOS CON PROPÓSITO</p><h2>Cada rol, en su lugar.</h2><p className="identity-hint">Dueño y Administrador gestionan usuarios. Caja incluye las funciones de Mesero. Cocina tiene su propio espacio de preparación.</p><div className="identity-role-list">{Object.entries(roles).map(([key, label]) => <span key={key}>{label}</span>)}</div><p className="identity-hint">Los permisos se comprueban también en el servidor.</p></section> : null}
        </div>}
        {((platform && activeSection === 'restaurants') || (canManage && activeSection === 'accounts')) && <section className="identity-card identity-directory" id={platform ? 'restaurants' : 'team'}><div className="identity-directory-heading"><div><p className="identity-eyebrow">{platform ? 'ESPACIOS CONECTADOS' : 'EQUIPO DEL RESTAURANTE'}</p><h2>{platform ? 'Restaurantes' : 'Usuarios y roles'}</h2></div><span className="identity-count">{rows.length} registros</span></div>
          {!rows.length ? <p className="identity-empty">{platform ? 'Tu primer restaurante empieza arriba. Crea una cuenta y vincula su espacio.' : 'Todavía no hay usuarios para mostrar.'}</p> : <ul className="identity-list">{rows.map(row => <li key={row.id}>{platform ? <>
            <div className="identity-row-heading"><div><h3>{row.name}</h3><p>{row.owners.map(owner => owner.email).join(', ') || 'Sin Dueño activo'}</p></div><span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span></div>
            <form className="identity-update" onSubmit={event => updateRestaurant(event, row.id)}><fieldset disabled={busy}><label>Estado<select name="is_active" defaultValue={String(row.is_active)} key={String(row.is_active)}><option value="true">Activo</option><option value="false">Inactivo</option></select></label><label>Vincular otro Dueño<select name="owner" defaultValue=""><option value="">Conservar asignación actual</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.email}</option>)}</select></label><button className="identity-secondary" type="submit">Guardar cambios</button></fieldset></form>
            {row.initial_owner && <div className="identity-status-control"><span className={`identity-badge ${row.initial_owner.is_active ? '' : 'identity-inactive'}`}>{row.initial_owner.is_active ? 'Dueño activo' : 'Dueño inactivo · acceso suspendido'}</span><button className="identity-secondary" disabled={busy} onClick={() => setPendingStatus({ target: row, active: !row.initial_owner.is_active, platformStatus: true })}>{row.initial_owner.is_active ? 'Suspender Dueño y acceso del restaurante' : 'Reactivar Dueño y acceso del restaurante'}</button></div>}
            {row.initial_owner && <form className="identity-update identity-role-update" aria-label={`Rol del primer Dueño de ${row.name}`} onSubmit={event => updateInitialOwnerRole(event, row.id)}>
              <p className="identity-hint">Primer Dueño: {row.initial_owner.email}. Solo el administrador global puede cambiar su rol. Debe quedar otro Dueño activo.</p>
              <fieldset disabled={busy || (row.initial_owner.role === 'OWNER' && row.owners.length < 2)}><label>Rol del primer Dueño<select name="role" defaultValue={row.initial_owner.role} key={row.initial_owner.role}>{Object.entries(roles).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><button className="identity-secondary" type="submit">Guardar rol del primer Dueño</button></fieldset>
            </form>}
          </> : <>
            <div className="identity-row-heading"><div className="identity-person"><span className="identity-avatar">{row.email.slice(0, 1).toUpperCase()}</span><div><h3>{row.email}</h3><p>Miembro de {user.restaurant.name}</p></div></div><span className="identity-badge">{roles[row.role]}</span></div>
            <div className="identity-status-control"><span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span><button className="identity-secondary" disabled={busy || row.is_initial_owner || (row.is_active && row.role === 'OWNER' && row.is_last_owner)} onClick={() => setPendingStatus({ target: row, active: !row.is_active, platformStatus: false })}>{row.is_active ? 'Desactivar usuario' : 'Activar usuario'}</button></div>
            {row.is_initial_owner && <p className="identity-hint">El estado del primer Dueño solo lo puede cambiar el administrador global.</p>}
            <form className="identity-update identity-role-update" aria-label={`Editar correo de ${row.email}`} onSubmit={event => updateEmail(event, row.id)}>
              <fieldset disabled={busy}><label>Correo de {row.email}<input name="email" type="email" required maxLength={150} autoComplete="off" value={emailDrafts[row.id] ?? row.email} onChange={event => setEmailDrafts(current => ({ ...current, [row.id]: event.target.value }))} /></label><button className="identity-secondary" type="submit">Guardar correo</button></fieldset>
            </form>
            <form className="identity-update identity-role-update" aria-label={`Cambiar rol de ${row.email}`} onSubmit={event => updateRole(event, row.id)}>
              {(row.is_initial_owner || row.is_last_owner) && <p className="identity-hint">{row.is_initial_owner ? 'Primer Dueño protegido: solo el administrador global puede cambiar su rol de Dueño.' : 'Debe conservarse al menos un Dueño activo. Asigna otro antes de cambiar este rol.'}</p>}
              <fieldset disabled={busy || (row.role === 'OWNER' && (row.is_initial_owner || row.is_last_owner))}><label>Rol de {row.email}<select name="role" defaultValue={row.role} key={row.role}>{Object.entries(roles).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><button className="identity-secondary" type="submit">Guardar rol</button></fieldset>
            </form>
          </>}</li>)}</ul>}
        </section>}
        {canManage && activeSection === 'zones' && <Zones key={`${user.id}-${user.role}`} refreshKey={historyVersion} onAccessError={handleError} />}
        {(platform || canManage) && activeSection === 'history' && <History key={`${user.id}-${user.role}`} refreshKey={historyVersion} />}
        {activeSection === 'access' && <section className="identity-access" id="access"><h2>Tus módulos autorizados</h2><div>{user.modules.map(module => <span key={module}>{labels[module]}</span>)}</div>{!platform && <p>Los módulos operativos se incorporarán en sus sprints correspondientes.</p>}</section>}
        <footer className="identity-footer">NEXO · Cada conexión cuenta.</footer>
      </div>
    </main>
    {pendingStatus && <div className="identity-confirm-overlay"><section className="identity-card identity-confirm" role="dialog" aria-modal="true" aria-labelledby="status-confirm-title" aria-describedby="status-confirm-description" onKeyDown={event => {
      if (event.key === 'Escape') setPendingStatus(null)
      if (event.key === 'Tab') {
        const buttons = event.currentTarget.querySelectorAll('button')
        if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[1].focus() }
        else if (!event.shiftKey && document.activeElement === buttons[1]) { event.preventDefault(); buttons[0].focus() }
      }
    }}>
      <h2 id="status-confirm-title">{pendingStatus.active ? 'Confirmar activación' : 'Confirmar desactivación'}</h2>
      <p id="status-confirm-description" className="identity-hint">{pendingStatus.platformStatus ? pendingStatus.target.initial_owner.email : pendingStatus.target.email}. {pendingStatus.platformStatus && !pendingStatus.active ? 'Todo el restaurante perderá el acceso y sus sesiones se cerrarán. Se conservarán los estados individuales y los históricos.' : pendingStatus.active ? 'Podrá iniciar sesión nuevamente si su restaurante tiene acceso activo. Los demás usuarios conservarán su estado.' : 'No podrá iniciar sesión y sus sesiones actuales se cerrarán. Su información histórica se conservará.'}</p>
      <div className="identity-status-control"><button className="identity-secondary" autoFocus onClick={() => setPendingStatus(null)}>Cancelar</button><button className="identity-primary" onClick={() => updateStatus(pendingStatus.target, pendingStatus.active, pendingStatus.platformStatus)}>Confirmar</button></div>
    </section></div>}
  </div>
}
