import { useEffect, useState } from 'react'
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
  async function saveProduct(event, row) {
    event.preventDefault()
    const values = Object.fromEntries(new FormData(event.currentTarget))
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await api(`products/${row.id}/`, { method: 'PATCH', body: JSON.stringify(values) })
      setEditing(null)
      setNotice('Producto actualizado correctamente.')
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
  </div>
}
