const base = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export async function api(path, options = {}) {
  const token = sessionStorage.getItem('nexo-token')
  const response = await fetch(`${base}/api/${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  const data = response.status === 204 ? null : await response.json()
  if (!response.ok) {
    const error = new Error(data.detail || Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(' ') : value}`).join(' · '))
    error.status = response.status
    throw error
  }
  return data
}
