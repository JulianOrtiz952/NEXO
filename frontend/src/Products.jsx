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

  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal }
    const request = manage
      ? Promise.all([api('products/', options), api('categories/', options)])
      : api('menu/', options).then(result => [result.products, []])
    request.then(([products, categories]) => {
      if (!controller.signal.aborted) setData({ products, categories: categories.filter(row => row.is_active) })
    }).catch(problem => {
      if (!controller.signal.aborted) {
        setData(null)
        setError(problem.message)
      }
    })
    return () => controller.abort()
  }, [manage, revision])

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
      {data && data.categories.length === 0 && <p className="identity-hint">Para registrar un producto, primero crea o activa una <a href="#categories">categoría</a>.</p>}
      <form className="identity-form" onSubmit={create}>
        <fieldset disabled={saving || !data?.categories.length}>
          <label>Nombre<input name="name" required maxLength={160} /></label>
          <label>Precio en COP<AmountInput name="price" labelId="price-format-hint" /></label>
          <small id="price-format-hint">Ejemplos: 1,000 · 1'000,000 · 11,999.85. Usa punto para los decimales.</small>
          <label>Categoría<select name="category" required defaultValue=""><option value="" disabled>Selecciona una categoría</option>{data?.categories.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
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
        </li>)}</ul>}
    </section>
  </div>
}
