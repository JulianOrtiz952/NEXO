import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'
import './Identity.css'
const labels = { users: 'Usuarios', tables: 'Mesas', kitchen: 'Cocina', menu: 'Carta', cashier: 'Caja', restaurants: 'Restaurantes' }
const roles = { OWNER: 'Dueño', ADMIN: 'Administrador', CASHIER: 'Caja', WAITER: 'Mesero', KITCHEN: 'Cocina' }

export default function Identity() {
  const [user, setUser] = useState(null)
  const [rows, setRows] = useState([])
  const [owners, setOwners] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const revision = useRef(0)
  function clearAccess(error) {
    revision.current += 1
    setUser(null)
    setRows([])
    setOwners([])
    setMessage(error.message)
    if (error.status === 401 || error.status === 403) sessionStorage.removeItem('nexo-token')
  }
  async function refresh() {
    const current = ++revision.current
    try {
      const profile = await api('auth/me/')
      if (current !== revision.current) return false
      setUser(profile)
      setRows([])
      setOwners([])
      const path = profile.modules.includes('users') ? 'users/' : profile.modules.includes('restaurants') ? 'platform/restaurants/' : null
      const [updatedRows, candidates] = await Promise.all([path ? api(path) : [], profile.role === 'PLATFORM_ADMIN' ? api('platform/owners/') : []])
      if (current !== revision.current) return false
      setRows(updatedRows)
      setOwners(candidates)
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
  async function logout() {
    try { await api('auth/logout/', { method: 'POST' }) }
    catch (error) { await handleError(error); return }
    revision.current += 1
    setUser(null); setRows([]); setOwners([])
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
  if (!user) return <main className="identity-gate"><a className="welcome-logo" href="/">NEX<span>O</span></a><h1>Tu espacio en NEXO</h1><p role="status">{message || 'Validando tu acceso…'}</p><a className="identity-primary" href="/login">Iniciar sesión →</a></main>
  const platform = user.role === 'PLATFORM_ADMIN'
  const canManage = user.modules.includes('users')
  return <div className="identity-shell">
    <aside className="identity-sidebar">
      <a className="identity-brand" href="/">NEX<span>O</span></a><p className="identity-caption">CADA CONEXIÓN CUENTA</p>
      <p className="identity-section-label">TU ESPACIO</p>
      <nav aria-label="Gestión autorizada">
        {platform ? <><a href="#accounts">◎ <span>Futuros Dueños</span></a><a href="#restaurants">▦ <span>Restaurantes</span></a></> : canManage ? <a href="#accounts">◎ <span>Usuarios y roles</span></a> : <a href="#access">◇ <span>Mi acceso</span></a>}
      </nav>
      <div className="identity-side-note"><span>Una operación conectada.</span><p>{platform ? 'Cada restaurante, con su propio equipo y su propio espacio.' : 'Las personas correctas, en cada lugar de tu restaurante.'}</p></div>
      <div className="identity-profile"><span className="identity-avatar">{user.email.slice(0, 1).toUpperCase()}</span><div><strong>{roles[user.role] || 'Administrador global'}</strong><small>{user.email}</small></div></div>
      <button className="identity-logout" onClick={logout}>Cerrar sesión ↗</button>
    </aside>
    <main className="identity-main">
      <header className="identity-topbar"><span>NEXO / {platform ? 'Plataforma' : user.restaurant.name}</span><span className="identity-session">Sesión de 1 hora</span></header>
      <div className="identity-content">
        <header className="identity-heading"><p className="identity-eyebrow">{platform ? 'ADMINISTRACIÓN DE PLATAFORMA' : 'TU EQUIPO, EN SINTONÍA'}</p><h1>{platform ? 'Conecta cada restaurante.' : canManage ? 'Personas que hacen equipo.' : 'Bienvenido a tu espacio.'}</h1><p>{platform ? 'Crea la cuenta del Dueño y vincúlala a su restaurante, desde un mismo lugar.' : canManage ? `Administra los accesos de ${user.restaurant.name}. Cada persona, con el rol que necesita.` : 'Tu acceso está asociado únicamente a tu restaurante.'}</p></header>
        <div className="identity-summary"><div><span>{platform ? 'RESTAURANTES' : 'RESTAURANTE'}</span><strong>{platform ? rows.length : user.restaurant.name}</strong></div><div><span>{platform ? 'DUEÑOS POR VINCULAR' : 'TU ROL'}</span><strong>{platform ? owners.length : roles[user.role]}</strong></div><div><span>ACCESO</span><strong>{platform ? 'Administración global' : 'Solo tu restaurante'}</strong></div></div>
        {message && <p className="identity-message" role="status">{message}</p>}
        {(platform || canManage) && <div className="identity-grid">
          <section className="identity-card" id="accounts"><div className="identity-card-heading"><span className="identity-step">{platform ? '01' : '◎'}</span><div><h2>{platform ? 'Crear cuenta del Dueño' : 'Crear usuario'}</h2><p>{platform ? 'La cuenta podrá ingresar cuando tenga un restaurante vinculado.' : 'El nuevo usuario pertenecerá a este restaurante.'}</p></div></div>
            <form className="identity-form" onSubmit={event => submit(event, platform ? 'owner' : 'user')}>
              <fieldset disabled={busy}><label>Correo electrónico<input name="email" required type="email" maxLength={150} autoComplete="off" placeholder="nombre@ejemplo.com" /></label><label>Contraseña inicial<input name="password" required type="password" autoComplete="new-password" placeholder="Crea una contraseña segura" /></label><small>Usa al menos 8 caracteres y evita contraseñas comunes o solo numéricas.</small>
                {!platform && <label>Rol del usuario<select name="role" defaultValue="WAITER">{Object.entries(roles).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
                <button className="identity-primary" type="submit">{busy ? 'Guardando…' : platform ? 'Crear cuenta del Dueño →' : 'Crear usuario →'}</button>
              </fieldset>
            </form>
          </section>
          {platform ? <section className="identity-card" id="new-restaurant"><div className="identity-card-heading"><span className="identity-step">02</span><div><h2>Vincular nuevo restaurante</h2><p>Selecciona el correo del Dueño que administrará este espacio.</p></div></div>
            <form className="identity-form" onSubmit={event => submit(event, 'restaurant')}><fieldset disabled={busy || !owners.length}><label>Nombre del restaurante<input name="name" required maxLength={160} placeholder="Nombre de tu restaurante" /></label><label>Dueño<select name="owner" required defaultValue=""><option value="" disabled>Selecciona un correo</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.email}</option>)}</select></label><button className="identity-primary" type="submit">Crear y vincular restaurante →</button></fieldset></form>
            {!owners.length && <p className="identity-hint">Primero crea una cuenta de Dueño. Solo aparecen cuentas activas sin restaurante.</p>}
          </section> : <section className="identity-card"><p className="identity-eyebrow">ACCESOS CON PROPÓSITO</p><h2>Cada rol, en su lugar.</h2><p className="identity-hint">Dueño y Administrador gestionan usuarios. Caja incluye las funciones de Mesero. Cocina tiene su propio espacio de preparación.</p><div className="identity-role-list">{Object.entries(roles).map(([key, label]) => <span key={key}>{label}</span>)}</div><p className="identity-hint">Los permisos se comprueban también en el servidor.</p></section>}
        </div>}
        {(platform || canManage) && <section className="identity-card identity-directory" id={platform ? 'restaurants' : 'team'}><div className="identity-directory-heading"><div><p className="identity-eyebrow">{platform ? 'ESPACIOS CONECTADOS' : 'EQUIPO DEL RESTAURANTE'}</p><h2>{platform ? 'Restaurantes' : 'Usuarios y roles'}</h2></div><span className="identity-count">{rows.length} registros</span></div>
          {!rows.length ? <p className="identity-empty">{platform ? 'Tu primer restaurante empieza arriba. Crea una cuenta y vincula su espacio.' : 'Todavía no hay usuarios para mostrar.'}</p> : <ul className="identity-list">{rows.map(row => <li key={row.id}>{platform ? <>
            <div className="identity-row-heading"><div><h3>{row.name}</h3><p>{row.owners.map(owner => owner.email).join(', ') || 'Sin Dueño activo'}</p></div><span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span></div>
            <form className="identity-update" onSubmit={event => updateRestaurant(event, row.id)}><fieldset disabled={busy}><label>Estado<select name="is_active" defaultValue={String(row.is_active)} key={String(row.is_active)}><option value="true">Activo</option><option value="false">Inactivo</option></select></label><label>Vincular otro Dueño<select name="owner" defaultValue=""><option value="">Conservar asignación actual</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.email}</option>)}</select></label><button className="identity-secondary" type="submit">Guardar cambios</button></fieldset></form>
          </> : <div className="identity-row-heading"><div className="identity-person"><span className="identity-avatar">{row.email.slice(0, 1).toUpperCase()}</span><div><h3>{row.email}</h3><p>Miembro de {user.restaurant.name}</p></div></div><span className="identity-badge">{roles[row.role]}</span></div>}</li>)}</ul>}
        </section>}
        <section className="identity-access" id="access"><h2>Tus módulos autorizados</h2><div>{user.modules.map(module => <span key={module}>{labels[module]}</span>)}</div>{!platform && <p>Los módulos operativos se incorporarán en sus sprints correspondientes.</p>}</section>
        <footer className="identity-footer">NEXO · Cada conexión cuenta.</footer>
      </div>
    </main>
  </div>
}
