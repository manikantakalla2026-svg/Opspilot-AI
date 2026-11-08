export type Service = { id: string; name: string; description: string; active: boolean; health: string; errors_24h: number; active_incidents: number }
export type Log = { id: string; service_id: string; service_name: string; severity: string; message: string; error_type: string; endpoint: string; received_at: string; metadata: Record<string, unknown> }
export type Incident = { id: string; service_name: string; title: string; severity: string; status: string; event_count: number; first_seen: string; last_seen: string }
export type Page<T> = { items: T[]; total: number }
export type Metrics = { services: number; healthy: number; unhealthy: number; errors_24h: number; active_incidents: number; severity: Record<string, number>; trend: { time: string; errors: number }[] }
// Public build-time URL only. Local development keeps Vite's existing /api proxy.
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')
if (base !== '/api') {
  const url = new URL(base)
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('VITE_API_BASE_URL must be an HTTPS API origin without a path, credentials, query or fragment.')
  }
}
export const apiUrl = (path: string) => `${base}${path}`
export async function api<T>(path: string, token: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': token }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000) })
  } catch (error) {
    throw new Error(error instanceof DOMException && error.name === 'TimeoutError'
      ? 'The API took too long to respond. If the demo is waking up, wait a moment and retry.'
      : 'Cannot reach the API. Check your connection and retry; the demo server may be waking up.')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(response.status === 401 ? 'Workspace token is invalid. Sign out and try again.' : typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Check your input and try again.`)
  }
  return response.status === 204 ? undefined as T : response.json()
}
