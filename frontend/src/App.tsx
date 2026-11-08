import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api, apiUrl } from './services/api'
import type { Service, Log, Incident, Page, Metrics } from './services/api'
import './App.css'
import IncidentAnalysis from './IncidentAnalysis'

type View = 'Overview' | 'Services' | 'Live logs' | 'Incidents' | 'QuickCart simulator'
const views: View[] = ['Overview', 'Services', 'Live logs', 'Incidents', 'QuickCart simulator']
const symbols = ['◈', '▦', '≡', '⚑', '▷']
const time = (value: string) => new Date(value).toLocaleString()
const tag = (value: string) => <span className={`tag ${value.toLowerCase()}`}>{value}</span>

function Trend({ data, asOf }: { data: Metrics['trend']; asOf: string }) {
  const end = new Date(asOf); end.setMinutes(0, 0, 0)
  const counts = Array.from({ length: 24 }, (_, i) => {
    const hour = new Date(end.getTime() - (23 - i) * 3600000)
    return { hour, count: data.find(d => new Date(d.time).getTime() === hour.getTime())?.errors ?? 0 }
  })
  const max = Math.max(1, ...counts.map(d => d.count))
  return <div className="chart" role="img" aria-label="Hourly errors over the last 24 hours"><div className="bars">{counts.map(d => <div className="bar-column" key={d.hour.toISOString()} title={`${d.hour.toLocaleTimeString()}: ${d.count} errors`}><span style={{ height: `${Math.max(d.count ? 3 : 0, d.count / max * 100)}%` }} /></div>)}</div><div className="chart-axis"><span>24 hours ago</span><span>Hourly error volume · peak {max === 1 && counts.every(d => !d.count) ? 0 : max}</span><span>Now</span></div></div>
}

function App() {
  const requestVersion = useRef(0)
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [token, setToken] = useState(() => sessionStorage.getItem('opspilot-token') ?? '')
  const [access, setAccess] = useState('')
  const [accessError, setAccessError] = useState('')
  const [view, setView] = useState<View>('Overview')
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [services, setServices] = useState<Page<Service>>({ items: [], total: 0 })
  const [logs, setLogs] = useState<Page<Log>>({ items: [], total: 0 })
  const [incidents, setIncidents] = useState<Page<Incident>>({ items: [], total: 0 })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [updated, setUpdated] = useState('')
  const [asOf, setAsOf] = useState('')
  const [busy, setBusy] = useState(false)
  const [credential, setCredential] = useState('')
  const [editing, setEditing] = useState<Service | null>(null)
  const [form, setForm] = useState({ name: '', description: '', active: true })
  const [filter, setFilter] = useState({ service: '', severity: '', q: '', since: '' })
  const [query, setQuery] = useState('')
  const [logOffset, setLogOffset] = useState(0)
  const [incidentOffset, setIncidentOffset] = useState(0)
  const [serviceOffset, setServiceOffset] = useState(0)
  const [incidentStatus, setIncidentStatus] = useState('')
  const [simulationService, setSimulationService] = useState('')
  const [scenario, setScenario] = useState('payment_timeout')
  const [health, setHealth] = useState('Checking API / database')

  const load = useCallback(async () => {
    if (!token) return
    const version = ++requestVersion.current
    try {
      const [m, s, l, i] = await Promise.all([
        api<Metrics>('/dashboard', token), api<Page<Service>>(`/services?limit=50&offset=${serviceOffset}`, token),
        api<Page<Log>>(`/logs?limit=25&offset=${logOffset}${query}`, token),
        api<Page<Incident>>(`/incidents?limit=25&offset=${incidentOffset}${incidentStatus ? `&status=${incidentStatus}` : ''}`, token),
      ])
      if (version !== requestVersion.current) return
      setMetrics(m); setServices(s); setLogs(l); setIncidents(i); setUpdated(new Date().toLocaleTimeString()); setAsOf(new Date().toISOString()); setError(''); setHealth('API + Neon connected')
      setSelectedIncident(current => current ? i.items.find(item => item.id === current.id) ?? current : null)
    } catch (e) { if (version === requestVersion.current) { setError((e as Error).message); setHealth('Connection needs attention') } }
  }, [token, query, logOffset, incidentOffset, serviceOffset, incidentStatus])
  useEffect(() => {
    const lifecycle = new AbortController()
    const requests = requestVersion
    const tick = () => { if (!lifecycle.signal.aborted && !document.hidden) void load() }
    const initial = setTimeout(tick, 0)
    const interval = setInterval(tick, 5000)
    return () => { lifecycle.abort(); ++requests.current; clearTimeout(initial); clearInterval(interval) }
  }, [load])
  useEffect(() => {
    void Promise.all(['/health', '/health/db'].map(p => fetch(apiUrl(p), { signal: AbortSignal.timeout(60000) }).then(r => r.ok)))
      .then(results => setHealth(results.every(Boolean) ? 'API + Neon connected' : 'Connection needs attention'))
      .catch(() => setHealth('API unreachable'))
  }, [])

  async function action(task: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('')
    try { await task(); await load() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setAccessError('')
    try {
      const value = access.trim()
      await api<Metrics>('/dashboard', value)
      sessionStorage.setItem('opspilot-token', value); setToken(value); setAccess(''); setError(''); setNotice('')
    } catch (e) { setAccessError((e as Error).message) }
    finally { setBusy(false) }
  }
  async function saveService(event: FormEvent) {
    event.preventDefault()
    await action(async () => {
      if (editing) { await api(`/services/${editing.id}`, token, 'PUT', form); setNotice('Service updated') }
      else { const created = await api<{ ingestion_key: string; id: string }>('/services', token, 'POST', { name: form.name, description: form.description }); setCredential(created.ingestion_key); setSimulationService(created.id); setNotice('Service registered. Save the ingestion key shown below.') }
      setForm({ name: '', description: '', active: true }); setEditing(null)
    })
  }
  function applyFilters(event: FormEvent) {
    event.preventDefault(); const params = new URLSearchParams()
    if (filter.service) params.set('service_id', filter.service)
    if (filter.severity) params.set('severity', filter.severity)
    if (filter.q) params.set('q', filter.q)
    if (filter.since) params.set('since', new Date(filter.since).toISOString())
    setLogOffset(0); setQuery(`&${params}`)
  }
  const serviceTable = <div className="table-wrap"><table><thead><tr><th>Service</th><th>Health</th><th>Errors / 24h</th><th>Active incidents</th>{view === 'Services' && <th>Actions</th>}</tr></thead><tbody>{services.items.map(s => <tr key={s.id}><td><strong>{s.name}</strong><small>{s.description || 'No description'}</small><small className="mono">{s.id}</small></td><td>{tag(s.health)}</td><td>{s.errors_24h}</td><td>{s.active_incidents}</td>{view === 'Services' && <td className="actions"><button disabled={busy} onClick={() => { setEditing(s); setForm({ name: s.name, description: s.description, active: s.active }) }}>Edit</button><button disabled={busy} onClick={() => void action(async () => { const result = await api<{ ingestion_key: string }>(`/services/${s.id}/rotate-key`, token, 'POST'); setCredential(result.ingestion_key); setNotice(`New key for ${s.name}; previous key is revoked`) })}>Rotate key</button><button disabled={busy || !s.active} onClick={() => { if (confirm(`Deactivate ${s.name}? History is retained and ingestion will stop.`)) void action(async () => { await api(`/services/${s.id}`, token, 'DELETE'); setNotice('Service deactivated; history retained') }) }}>Deactivate</button></td>}</tr>)}</tbody></table>{!services.items.length && <p className="empty" role="status">{!metrics && !error ? 'Loading services…' : 'No services yet. Register your first service to begin receiving logs.'}</p>}</div>
  const incidentTable = <div className="table-wrap"><table><thead><tr><th>Incident / service</th><th>Severity</th><th>Status</th><th>Events</th><th>Last seen</th></tr></thead><tbody>{incidents.items.map(i => <tr key={i.id}><td><strong>{i.title}</strong><small>{i.service_name}</small><button onClick={() => setSelectedIncident(i)}>Details / Analyze with AI</button></td><td>{tag(i.severity)}</td><td><select aria-label={`Status for ${i.title}`} disabled={busy || i.status === 'Resolved'} value={i.status} onChange={e => void action(async () => { await api(`/incidents/${i.id}`, token, 'PATCH', { status: e.target.value }); setNotice('Incident status updated') })}>{['Open', 'Investigating', 'Resolved'].map(s => <option key={s}>{s}</option>)}</select></td><td>{i.event_count}</td><td>{time(i.last_seen)}</td></tr>)}</tbody></table>{!incidents.items.length && <p className="empty" role="status">{!metrics && !error ? 'Loading incidents…' : 'No incidents match. Five similar errors within two minutes open an incident automatically.'}</p>}</div>
  const pager = (offset: number, total: number, size: number, change: (n: number) => void) => <div className="pager"><span>{total ? `${offset + 1}–${Math.min(offset + size, total)} of ${total}` : '0 results'}</span><button disabled={offset === 0 || busy} onClick={() => change(Math.max(0, offset - size))}>Previous</button><button disabled={offset + size >= total || busy} onClick={() => change(offset + size)}>Next</button></div>

  if (!token) return <div className="access-shell"><form className="panel access" onSubmit={event => void login(event)} aria-busy={busy}><div className="brand"><b>OP</b> OpsPilot AI</div><p className="eyebrow">DEVELOPER OPERATIONS</p><h1>Open your workspace.</h1><p>Enter the demo workspace token provided by the operator. This shared workspace contains demonstration data.</p><label>Workspace token<input type="password" required value={access} onChange={e => setAccess(e.target.value)} autoComplete="off" aria-describedby="workspace-help" disabled={busy} /></label>{accessError && <p className="alert error" role="alert">{accessError}</p>}<button className="primary" disabled={busy || !access.trim()}>{busy ? 'Connecting…' : 'Connect workspace →'}</button><small id="workspace-help">Your token is kept in this tab’s session storage until you sign out.</small><div className={`connection ${health === 'API + Neon connected' ? '' : 'pending'}`} role="status">● {health}</div></form></div>
  return <div className="layout"><a className="skip-link" href="#workspace-main">Skip to workspace content</a><aside><div className="brand"><b>OP</b> OpsPilot AI</div><p className="nav-label">WORKSPACE</p><nav>{views.map((v, i) => <button key={v} aria-current={view === v ? 'page' : undefined} className={view === v ? 'selected' : ''} onClick={() => setView(v)}><span>{symbols[i]}</span>{v}</button>)}</nav><div className="sidebar-bottom"><span className={`connection ${health === 'API + Neon connected' ? '' : 'pending'}`} role="status">● {health}</span><small>Single demo workspace</small><button onClick={() => { ++requestVersion.current; sessionStorage.removeItem('opspilot-token'); setToken(''); setSelectedIncident(null); setMetrics(null); setCredential(''); setServices({ items: [], total: 0 }); setLogs({ items: [], total: 0 }); setIncidents({ items: [], total: 0 }); setAccessError(''); setError(''); setNotice(''); setView('Overview'); setEditing(null); setForm({ name: '', description: '', active: true }); setUpdated('') }}>Sign out</button></div></aside>
    <main id="workspace-main" tabIndex={-1}><header><div><span className="eyebrow">WORKSPACE / {view.toUpperCase()}</span><h1>{view === 'Overview' ? 'Operational overview' : view}</h1><p>Monitor your services. Catch failures. Investigate with evidence.</p></div><span className={`polling ${error ? 'pending' : ''}`}>{error ? '● Refresh failed' : '● Polling every 5s'}<br /><small>{updated ? `Last updated ${updated}` : 'Loading workspace…'}</small></span></header>
      {error && <div className="alert error" role="alert">{error}<button onClick={() => void load()}>Retry</button></div>}{notice && <div className="alert success" role="status">{notice}</div>}
      {credential && <div className="alert credential"><strong>Ingestion key — shown only this session</strong><code>{credential}</code><p>Send this as X-Ingestion-Key to POST /ingest/SERVICE_ID. Never commit it.</p><button onClick={() => setCredential('')}>Dismiss key</button></div>}
      {!metrics && !error && <p className="empty" role="status">Loading data from Neon…</p>}
      {view === 'Overview' && metrics && <><section className="metrics">{[['Active services', metrics.services, `${metrics.healthy} healthy · ${metrics.unhealthy} unhealthy`], ['Errors / 24 hours', metrics.errors_24h, 'ERROR + CRITICAL logs'], ['Active incidents', metrics.active_incidents, 'Open + investigating'], ['Critical incidents', metrics.severity.CRITICAL ?? 0, 'Unresolved critical failures']].map(([title, value, hint]) => <article className="metric" key={title}><span>{title}</span><strong>{value}</strong><small>{hint}</small></article>)}</section><section className="panel"><div className="section-head"><h2>Error activity</h2><span>Last 24 hours · received time</span></div><Trend data={metrics.trend} asOf={asOf} /></section><section className="panel"><div className="section-head"><h2>Service health</h2><button onClick={() => setView('Services')}>Manage services →</button></div>{serviceTable}</section><section className="panel"><div className="section-head"><h2>Recent incidents</h2><button onClick={() => setView('Incidents')}>View all →</button></div>{incidentTable}</section></>}
      {view === 'Services' && <><section className="panel"><h2>{editing ? `Edit ${editing.name}` : 'Register a service'}</h2><form className="service-form" onSubmit={saveService}><label>Service name<input required minLength={2} maxLength={100} placeholder="QuickCart Payments" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label><label>Description<input maxLength={500} placeholder="Checkout and payment processing" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label>{editing && <label className="check"><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} />Active</label>}<button disabled={busy} className="primary">{busy ? 'Saving…' : editing ? 'Save changes' : 'Register service'}</button>{editing && <button type="button" onClick={() => { setEditing(null); setForm({ name: '', description: '', active: true }) }}>Cancel</button>}</form></section><section className="panel"><h2>Registered services</h2>{serviceTable}{pager(serviceOffset, services.total, 50, setServiceOffset)}</section></>}
      {view === 'Live logs' && <section className="panel"><div className="section-head"><h2>Structured event stream</h2><span>Newest first · auto-refreshing</span></div><form className="filters" onSubmit={applyFilters}><select aria-label="Filter by service" value={filter.service} onChange={e => setFilter({ ...filter, service: e.target.value })}><option value="">All services on this page</option>{services.items.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select><select aria-label="Filter by severity" value={filter.severity} onChange={e => setFilter({ ...filter, severity: e.target.value })}><option value="">All severities</option>{['INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(s => <option key={s}>{s}</option>)}</select><input aria-label="Search log messages" placeholder="Search messages…" maxLength={100} value={filter.q} onChange={e => setFilter({ ...filter, q: e.target.value })} /><input aria-label="Logs since" type="datetime-local" value={filter.since} onChange={e => setFilter({ ...filter, since: e.target.value })} /><button>Apply filters</button></form><div className="table-wrap"><table><thead><tr><th>Received</th><th>Service</th><th>Level</th><th>Message / endpoint</th></tr></thead><tbody>{logs.items.map(l => <tr key={l.id}><td className="mono">{time(l.received_at)}</td><td>{l.service_name}</td><td>{tag(l.severity)}</td><td><strong>{l.message}</strong><small>{l.error_type} {l.endpoint}</small><details><summary>Metadata</summary><pre>{JSON.stringify(l.metadata, null, 2)}</pre></details></td></tr>)}</tbody></table>{!logs.items.length && <p className="empty" role="status">{!metrics && !error ? 'Loading logs…' : 'No matching logs. Send a structured log or run the QuickCart simulator.'}</p>}</div>{pager(logOffset, logs.total, 25, setLogOffset)}</section>}
      {view === 'Incidents' && <section className="panel"><div className="section-head"><h2>Detected incidents</h2><select aria-label="Filter incident status" value={incidentStatus} onChange={e => { setIncidentStatus(e.target.value); setIncidentOffset(0) }}><option value="">All statuses</option>{['Open', 'Investigating', 'Resolved'].map(s => <option key={s}>{s}</option>)}</select></div>{incidentTable}{pager(incidentOffset, incidents.total, 25, setIncidentOffset)}</section>}
      {view === 'QuickCart simulator' && <section className="panel simulator"><p className="eyebrow">CONTROLLED DEMONSTRATION</p><h2>QuickCart payment service</h2><p>Generate real, sanitized logs in Neon through the same ingestion and detection pipeline used by external services.</p><div className="simulation-rule"><strong>5 errors / 2 minutes → 1 incident</strong><p>Each run sends five failures, or three normal events. Runs stop automatically and are limited to one per service every 30 seconds.</p></div><label>Target service<select value={simulationService} onChange={e => setSimulationService(e.target.value)}><option value="">Select an active service</option>{services.items.filter(s => s.active).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Scenario<select value={scenario} onChange={e => setScenario(e.target.value)}><option value="payment_timeout">Payment gateway timeout</option><option value="database_timeout">Database connection timeout</option><option value="exception">Application exception</option><option value="normal">Normal payment</option></select></label><button className="primary" disabled={busy || !simulationService} onClick={() => void action(async () => { const result = await api<{ logs_created: number; incident_id: string | null }>('/simulator', token, 'POST', { service_id: simulationService, scenario }); setNotice(`${result.logs_created} logs persisted.${result.incident_id ? ' Incident created or updated — open Incidents to inspect.' : ' No incident triggered.'}`) })}>{busy ? 'Running bounded simulation…' : 'Run simulation →'}</button>{!services.items.some(s => s.active) && <p>Register an active service in Services first.</p>}</section>}
      {selectedIncident && <IncidentAnalysis key={selectedIncident.id} incident={selectedIncident} token={token} close={() => setSelectedIncident(null)} />}
      <footer>OpsPilot AI <span>Real API data · Neon PostgreSQL · threshold-based detection</span></footer>
    </main></div>
}
export default App

