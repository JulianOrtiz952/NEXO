import { useState } from 'react'
import { api } from './identityApi.js'
export default function Login() {
  const [visible, setVisible] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget))
    setBusy(true); setMessage('')
    sessionStorage.removeItem('nexo-token')
    try {
      const result = await api('auth/login/', { method: 'POST', body: JSON.stringify(data) })
      sessionStorage.setItem('nexo-token', result.token)
      window.location.assign('/app')
    } catch (error) { setMessage(error.message) }
    finally { setBusy(false) }
  }
  return (
<div className="login">
  <aside className="side">
    <a className="logo" href="/">NEXO</a>
    <h1>Tu operación.<br />Tu equipo.<br /><span>Todo conectado.</span></h1>
    <div className="ring" aria-hidden="true"></div>
  </aside>

  <main className="panel">
    <div className="card">
      <h2>Bienvenido de nuevo</h2>
      <p>Ingresa con tu cuenta. La sesión vence después de una hora.</p>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="email">Correo electrónico</label>
          <input id="email" name="email" required type="email" autoComplete="email" placeholder="tucorreo@ejemplo.com" />
        </div>
        <div className="field">
          <label htmlFor="pass">Contraseña</label>
          <input id="pass" name="password" required minLength={6} type={visible ? "text" : "password"} autoComplete="current-password" placeholder="Mínimo 6 caracteres" style={{ paddingRight: "6rem" }} />
          <button className="eye" type="button" onClick={() => setVisible(v => !v)} aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}>{visible ? "Ocultar" : "Mostrar"}</button>
        </div>
        <div className="err" role="status">{message}</div>
        <div className="meta">
          <span>Recuperación pendiente</span>
        </div>
        <button className="btn" type="submit" disabled={busy}>{busy ? 'Ingresando…' : 'Iniciar sesión'}</button>
      </form>
      <p className="alt">Solicita tu cuenta al administrador de tu restaurante.</p>
    </div>
  </main>
</div>

)
}
