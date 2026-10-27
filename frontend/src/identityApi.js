const base = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export async function api(path, options = {}) {
  const token = sessionStorage.getItem('nexo-token')
  const response = await fetch(`${base}/api/${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  let data = null
  if (response.status !== 204) {
    try { data = await response.json() }
    catch {
      // RNF-033: HTML error pages must not leak parser errors into the UI.
      const error = new Error('El servidor no pudo procesar la solicitud. Intenta de nuevo; si el problema continúa, contacta al administrador.')
      error.status = response.status
      throw error
    }
  }
  if (!response.ok) {
    const error = new Error(data.detail || Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(' ') : value}`).join(' · '))
    error.status = response.status
    throw error
  }
  return data
}
