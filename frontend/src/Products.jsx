import { useEffect, useRef, useState } from 'react'
import { api } from './identityApi.js'

import AmountInput from './AmountInput.jsx'
import { formatMoney, parseAmount } from './numberFormat.js'

export default function Products({ manage }) {
  const [data, setData] = useState(null)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(null)
  const [description, setDescription] = useState('')
  const [pendingStatus, setPendingStatus] = useState(null)
  const statusTrigger = useRef(null)

  function closeStatus() {
    setPendingStatus(null)
    statusTrigger.current?.focus()
  }

  // RF-028, RNF-032: explicit availability target and confirmation, never toggle stale server state.
  async function saveStatus(row) {
    closeStatus()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const updated = await api(`products/${row.id}/status/`, { method: 'PATCH', body: JSON.stringify({ is_active: !row.is_active }) })
      setData(current => ({ ...current, products: current.products.map(product => product.id === row.id ? updated : product) }))
      setNotice(updated.is_active ? 'Producto activado correctamente.' : 'Producto desactivado correctamente.')
    } catch (problem) { setError(problem.message) }
    finally { setSaving(false) }
  }

  // RF-025: send only the description so unrelated product fields stay intact.
  async function saveDescription(event, row) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const updated = await api(`products/${row.id}/description/`, { method: 'PATCH', body: JSON.stringify({ description }) })
      setData(current => ({ ...current, products: current.products.map(product => product.id === updated.id ? updated : product) }))
      setEditing(null)
      setNotice('Descripción guardada correctamente.')
    } catch (problem) {
      setError(problem.message)
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal }
    const request = manage
      ? Promise.all([api('products/', options), api('categories/', options)])
      : api('menu/', options).then(result => [result.products, []])
    request.then(([products, categories]) => {
      if (!controller.signal.aborted) setData({ products, categories })
    }).catch(problem => {
      if (!controller.signal.aborted) {
        setData(null)
        setError(problem.message)
      }
    })
    return () => controller.abort()
  }, [manage, revision])

  // RF-026: the information editor cannot change price or availability.
  async function saveProduct(event, row, operation = 'details') {
    event.preventDefault()
    const values = Object.fromEntries(new FormData(event.currentTarget))
    if (operation === 'price') values.price = parseAmount(values.price)
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await api(`products/${row.id}/${operation === 'price' ? 'price/' : ''}`, { method: 'PATCH', body: JSON.stringify(values) })
      setEditing(null)
      setNotice(operation === 'price' ? 'Precio actualizado correctamente.' : 'Producto actualizado correctamente.')
      setRevision(value => value + 1)
    } catch (problem) { setError(problem.message) }
    finally { setSaving(false) }
  }

  async function create(event) {
    event.preventDefault()
    const form = event.currentTarget
    const fields = Object.fromEntries(new FormData(form))
    fields.price = parseAmount(fields.price)
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await api('products/', { method: 'POST', body: JSON.stringify({ ...fields, is_active: fields.is_active === 'true' }) })
      form.reset()
      setNotice('Producto registrado correctamente.')
      setRevision(value => value + 1)
    } catch (problem) {
      setError(problem.message)
      setRevision(value => value + 1)
    } finally {
      setSaving(false)
    }
  }

  return <div className="zones-layout">
    {manage && <section className="identity-card">
      <h2>Registrar producto</h2>
      {data && !data.categories.some(row => row.is_active) && <p className="identity-hint">Para registrar un producto, primero crea o activa una <a href="#categories">categoría</a>.</p>}
      <form className="identity-form" onSubmit={create}>
        <fieldset disabled={saving || !data?.categories.some(row => row.is_active)}>
          <label>Nombre<input name="name" required maxLength={160} /></label>
          <label>Descripción (opcional)<textarea name="description" rows={3} placeholder="Cuenta qué incluye este producto…" /></label>
          <label>Precio en COP<AmountInput name="price" labelId="price-format-hint" /></label>
          <small id="price-format-hint">Ejemplos: 1,000 · 1'000,000 · 11,999.85. Usa punto para los decimales.</small>
          <label>Categoría<select name="category" required defaultValue=""><option value="" disabled>Selecciona una categoría</option>{data?.categories.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
          <label>Estado<select name="is_active" required defaultValue=""><option value="" disabled>Selecciona un estado</option><option value="true">Activo</option><option value="false">Inactivo</option></select></label>
          <button className="identity-primary" type="submit">{saving ? 'Guardando…' : 'Registrar producto'}</button>
        </fieldset>
      </form>
    </section>}
    {notice && <p role="status" className="identity-message">{notice}</p>}
    {error && <div role="alert"><p className="identity-message">{error}</p><button className="identity-secondary" onClick={() => { setError(''); setRevision(value => value + 1) }}>Actualizar lista</button></div>}
    <section className="identity-card">
      <h2>{manage ? 'Productos registrados' : 'Carta del restaurante'}</h2>
      {!data ? !error && <p role="status" className="identity-hint">Cargando productos…</p>
        : !data.products.length ? <p className="identity-empty">{manage ? 'Aún no hay productos registrados.' : 'No hay productos disponibles en la carta.'}</p>
        : <ul className="identity-list">{data.products.map(row => <li key={row.id}>
          <div className="identity-row-heading"><div><h3>{row.name}</h3><p>{row.category_name} · {formatMoney(row.price)}</p></div>
            {manage && <span className={`identity-badge ${row.is_active ? '' : 'identity-inactive'}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span>}</div>
          {row.description && <p className="product-description">{row.description}</p>}
          {manage && <div className="identity-status-control"><button className="identity-secondary" disabled={saving} aria-label={`${row.is_active ? 'Desactivar' : 'Activar'} producto ${row.name}`} onClick={event => { statusTrigger.current = event.currentTarget; setPendingStatus(row) }}>{row.is_active ? 'Desactivar' : 'Activar'} producto</button></div>}
          {manage && (editing === `${row.id}:price` ? <form className="identity-form product-description-form" onSubmit={event => saveProduct(event, row, 'price')}>
            <fieldset disabled={saving}>
              <label>Nuevo precio de {row.name}<AmountInput name="price" labelId={`price-hint-${row.id}`} defaultValue={row.price} /></label>
              <small id={`price-hint-${row.id}`}>COP. Usa punto para los decimales. Ejemplo: 11,999.85.</small>
              <div className="identity-status-control"><button className="identity-primary" type="submit">{saving ? 'Guardando…' : 'Guardar precio'}</button><button className="identity-secondary" type="button" onClick={() => setEditing(null)}>Cancelar precio</button></div>
            </fieldset>
          </form> : <div className="identity-status-control"><button className="identity-secondary" disabled={saving} aria-label={`Cambiar precio de ${row.name}`} onClick={() => { setEditing(`${row.id}:price`); setNotice('') }}>Cambiar precio</button></div>)}
          {manage && (editing === `${row.id}:details` ? <form key={row.id} className="identity-form product-description-form" onSubmit={event => saveProduct(event, row)}>
            <fieldset disabled={saving}>
              <label>Nombre de {row.name}<input autoFocus name="name" required maxLength={160} defaultValue={row.name} /></label>
              <label>Descripción del producto<textarea name="description" rows={3} defaultValue={row.description} /></label>
              <label>Categoría del producto<select name="category" required defaultValue={row.category}>{data.categories.filter(category => category.is_active || category.id === row.category).map(category => <option key={category.id} value={category.id}>{category.name}{category.is_active ? '' : ' (inactiva)'}</option>)}</select></label>
              <small>El precio y la disponibilidad se conservan.</small>
              <div className="identity-status-control"><button className="identity-primary" type="submit">{saving ? 'Guardando…' : 'Guardar producto'}</button><button className="identity-secondary" type="button" onClick={() => setEditing(null)}>Cancelar edición</button></div>
            </fieldset>
          </form> : <div className="identity-status-control"><button className="identity-secondary" disabled={saving} aria-label={`Editar producto ${row.name}`} onClick={() => { setEditing(`${row.id}:details`); setNotice('') }}>Editar producto</button></div>)}
          {manage && (editing === row.id ? <form className="identity-form product-description-form" onSubmit={event => saveDescription(event, row)}>
            <fieldset disabled={saving}>
              <label>Descripción de {row.name}<textarea autoFocus rows={4} value={description} onChange={event => setDescription(event.target.value)} /></label>
              <small>Puedes dejarla vacía. Solo se modificará la descripción.</small>
              <div className="identity-status-control"><button className="identity-primary" type="submit">{saving ? 'Guardando…' : 'Guardar descripción'}</button><button className="identity-secondary" type="button" onClick={() => setEditing(null)}>Cancelar</button></div>
            </fieldset>
          </form> : <div className="identity-status-control"><button className="identity-secondary" disabled={saving} aria-label={`Editar descripción de ${row.name}`} onClick={() => { setEditing(row.id); setDescription(row.description); setNotice('') }}>Editar descripción</button></div>)}
        </li>)}</ul>}
    </section>
    {pendingStatus && <div className="identity-confirm-overlay"><section className="identity-card identity-confirm" role="dialog" aria-modal="true" aria-labelledby="product-status-title" aria-describedby="product-status-description" onKeyDown={event => {
      if (event.key === 'Escape') closeStatus()
      if (event.key === 'Tab') {
        const buttons = event.currentTarget.querySelectorAll('button')
        if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[1].focus() }
        else if (!event.shiftKey && document.activeElement === buttons[1]) { event.preventDefault(); buttons[0].focus() }
      }
    }}><h2 id="product-status-title">{pendingStatus.is_active ? 'Desactivar producto' : 'Activar producto'}</h2><p id="product-status-description" className="identity-hint">¿Quieres {pendingStatus.is_active ? 'desactivar' : 'activar'} {pendingStatus.name}? {pendingStatus.is_active ? 'Dejará de mostrarse en la carta.' : 'Se mostrará en la carta si su categoría está activa.'} Su registro y su historial se conservarán.</p><div className="identity-status-control"><button className="identity-secondary" autoFocus onClick={closeStatus}>Cancelar</button><button className="identity-primary" onClick={() => saveStatus(pendingStatus)}>Confirmar {pendingStatus.is_active ? 'desactivación' : 'activación'}</button></div></section></div>}
  </div>
}
