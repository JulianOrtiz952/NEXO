import { useState } from 'react'
export default function Login() {
  const [visible, setVisible] = useState(false)
  const [message, setMessage] = useState('')
  function submit(event) {
    event.preventDefault()
    setMessage('El inicio de sesión todavía no está habilitado. No se enviaron tus credenciales.')
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
      <p>Vista previa del acceso. La autenticación estará disponible próximamente.</p>
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
          <label><input type="checkbox" /> Recordarme</label>
          <span>Recuperación pendiente</span>
        </div>
        <button className="btn" type="submit">Iniciar sesión</button>
      </form>
      <p className="alt">¿Aún no tienes cuenta? <span>Registro próximamente</span></p>
    </div>
  </main>
</div>

)
}
