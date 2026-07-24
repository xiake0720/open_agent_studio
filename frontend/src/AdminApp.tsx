import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, Bot, ChartNoAxesCombined, ChevronRight, CircleGauge,
  Database, Loader2, LogOut, Menu, MessageSquareText, Plus, RefreshCw, Save, Search,
  ShieldCheck, Users, X,
} from 'lucide-react'
import { adminApi, ApiError } from './lib/api'
import type {
  AdminConversation, AdminConversationDetail, AdminException, AdminManagedUser,
  AdminModel, AdminModelPayload, AdminOverview, AdminTokenStats, AdminUser,
  CaptchaChallenge,
} from './types'
import { formatDateTime } from './utils/format'

type Section = 'overview' | 'users' | 'tokens' | 'models' | 'conversations' | 'exceptions'

const NAV: Array<{ id: Section; label: string; icon: typeof CircleGauge }> = [
  { id: 'overview', label: '运行概览', icon: CircleGauge },
  { id: 'users', label: '用户管理', icon: Users },
  { id: 'tokens', label: 'Token 统计', icon: ChartNoAxesCombined },
  { id: 'models', label: '模型管理', icon: Bot },
  { id: 'conversations', label: '会话管理', icon: MessageSquareText },
  { id: 'exceptions', label: '异常管理', icon: AlertTriangle },
]

const EMPTY_MODEL: AdminModelPayload = {
  provider: '', display_name: '', model_id: '', base_url: '', api_key: '', api_key_env: '',
  api_shape: 'chat_completions', support_streaming: true, support_tools: false,
  support_image: false, enabled: true, extra_body_json: '',
}

type AuthErrorData = {
  captcha_required?: boolean
  refresh_captcha?: boolean
}

function errorText(error: unknown) {
  return error instanceof ApiError || error instanceof Error ? error.message : '操作失败'
}

function number(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function dateInput(daysAgo = 0) {
  const date = new Date()
  date.setDate(date.getDate() - daysAgo)
  return date.toISOString().slice(0, 10)
}

function AdminLogin({ onLogin }: { onLogin: (user: AdminUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [captchaCode, setCaptchaCode] = useState('')
  const [captcha, setCaptcha] = useState<CaptchaChallenge | null>(null)
  const [captchaLoading, setCaptchaLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const refreshCaptcha = useCallback(async () => {
    setCaptchaLoading(true)
    try {
      setCaptcha(await adminApi.getCaptcha())
      setCaptchaCode('')
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setCaptchaLoading(false)
    }
  }, [])
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true); setError('')
    try {
      const result = await adminApi.login({
        username,
        password,
        captcha_id: captcha?.captcha_id,
        captcha_code: captchaCode || undefined,
      })
      onLogin(result.user)
    } catch (reason) {
      setError(errorText(reason))
      if (reason instanceof ApiError) {
        const data = reason.data as AuthErrorData | undefined
        if (data?.captcha_required) await refreshCaptcha()
      }
    } finally { setLoading(false) }
  }
  return <div className="admin-login">
    <form className="admin-login__card" onSubmit={submit}>
      <div className="admin-login__icon"><ShieldCheck size={28} /></div>
      <span className="admin-kicker">OPENAGENT CONTROL</span>
      <h1>管理后台</h1>
      <p>仅限系统管理员访问</p>
      <label>管理员账号<input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="请输入管理员账号" /></label>
      <label>密码<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" /></label>
      {captcha ? <div className="admin-captcha">
        <span>安全验证码</span>
        <div>
          <input value={captchaCode} onChange={(event) => setCaptchaCode(event.target.value.toUpperCase())} maxLength={12} placeholder="输入图中字符" required />
          <button type="button" onClick={() => void refreshCaptcha()} title="换一张验证码">
            {captchaLoading ? <Loader2 className="spin" size={18} /> : <img src={captcha.image_data_uri} alt="登录验证码" />}
            <RefreshCw size={13} />
          </button>
        </div>
        <small>密码连续错误多次，需要完成验证码校验。</small>
      </div> : null}
      {error ? <div className="admin-error">{error}</div> : null}
      <button className="admin-primary" disabled={loading || !username || !password || (!!captcha && !captchaCode)}>{loading ? '正在验证…' : '安全登录'}</button>
      <a href="/">返回智能体工作台</a>
    </form>
  </div>
}

function Overview({ data }: { data: AdminOverview | null }) {
  const cards = [
    ['注册用户', data?.users ?? 0, `${data?.active_users ?? 0} 个账号正常`, Users],
    ['累计 Token', data?.total_tokens ?? 0, '基于模型实际用量', Activity],
    ['会话总数', data?.conversations ?? 0, `${data?.runs ?? 0} 次 Agent 运行`, MessageSquareText],
    ['待处理异常', data?.unresolved_exceptions ?? 0, `${data?.failed_runs ?? 0} 次运行失败`, AlertTriangle],
  ] as const
  return <>
    <div className="admin-stats">{cards.map(([label, value, note, Icon]) => <article key={label}>
      <div><span>{label}</span><Icon size={19} /></div><strong>{number(value)}</strong><small>{note}</small>
    </article>)}</div>
    <section className="admin-panel admin-overview-note">
      <div className="admin-panel__title"><Database size={18} /><div><h2>数据采集状态</h2><p>管理数据来自业务数据库实时聚合</p></div></div>
      <div className="admin-health-grid"><span><i /> 用户与会话数据</span><span><i /> 模型运行与 Token</span><span><i /> 系统异常记录</span></div>
    </section>
  </>
}

function UsersView({ items, onToggle }: { items: AdminManagedUser[]; onToggle: (item: AdminManagedUser) => void }) {
  return <section className="admin-panel admin-table-wrap"><table><thead><tr><th>用户</th><th>会话</th><th>登录状态</th><th>注册时间</th><th>状态</th><th /></tr></thead>
    <tbody>{items.map(item => <tr key={item.id}><td><strong>{item.username}</strong><small>{item.id}</small></td><td>{item.conversation_count}</td><td>{item.last_login_at ? formatDateTime(item.last_login_at) : '从未登录'}{item.failed_login_attempts ? <small>{item.failed_login_attempts} 次失败</small> : null}</td><td>{formatDateTime(item.created_at)}</td><td><span className={`admin-status ${item.is_active ? 'ok' : 'off'}`}>{item.is_active ? '正常' : '已停用'}</span></td><td><button className="admin-quiet" onClick={() => onToggle(item)}>{item.is_active ? '停用' : '启用'}</button></td></tr>)}</tbody>
  </table>{items.length === 0 ? <div className="admin-empty">暂无用户</div> : null}</section>
}

function TokensView({ data, dateFrom, dateTo, onDateFrom, onDateTo }: { data: AdminTokenStats | null; dateFrom: string; dateTo: string; onDateFrom: (value: string) => void; onDateTo: (value: string) => void }) {
  const max = Math.max(1, ...(data?.by_time.map(item => item.total_tokens) || [1]))
  return <>
    <div className="admin-date-filter"><span>统计周期</span><label>开始<input type="date" value={dateFrom} onChange={event => onDateFrom(event.target.value)} /></label><span>至</span><label>结束<input type="date" value={dateTo} min={dateFrom} onChange={event => onDateTo(event.target.value)} /></label></div>
    <div className="admin-stats admin-stats--three"><article><span>输入 Token</span><strong>{number(data?.summary.input_tokens || 0)}</strong></article><article><span>输出 Token</span><strong>{number(data?.summary.output_tokens || 0)}</strong></article><article><span>总 Token</span><strong>{number(data?.summary.total_tokens || 0)}</strong></article></div>
    <div className="admin-split"><section className="admin-panel"><div className="admin-panel__title"><ChartNoAxesCombined size={18} /><div><h2>每日用量</h2><p>最近 30 天实际 Token 消耗</p></div></div><div className="token-chart">{data?.by_time.map(item => <div className="token-bar" key={item.date}><span style={{ height: `${Math.max(5, item.total_tokens / max * 100)}%` }} title={`${item.date}: ${number(item.total_tokens)}`} /><small>{item.date.slice(5)}</small></div>)}</div></section>
      <section className="admin-panel admin-table-wrap"><div className="admin-panel__title"><Bot size={18} /><div><h2>模型用量</h2><p>按模型聚合</p></div></div><table><thead><tr><th>模型</th><th>请求</th><th>输入</th><th>输出</th><th>总计</th></tr></thead><tbody>{data?.by_model.map(item => <tr key={item.model}><td><strong>{item.model}</strong></td><td>{item.requests}</td><td>{number(item.input_tokens)}</td><td>{number(item.output_tokens)}</td><td>{number(item.total_tokens)}</td></tr>)}</tbody></table></section></div>
  </>
}

function ModelEditor({ item, onClose, onSave }: { item: AdminModel | null; onClose: () => void; onSave: (data: AdminModelPayload) => Promise<void> }) {
  const [form, setForm] = useState<AdminModelPayload>(item ? { provider:item.provider, display_name:item.display_name, model_id:item.model_id, base_url:item.base_url, api_key:'', api_key_env:item.api_key_env || '', api_shape:item.api_shape, support_streaming:item.support_streaming, support_tools:item.support_tools, support_image:item.support_image, enabled:item.enabled, extra_body_json:item.extra_body_json || '' } : EMPTY_MODEL)
  const [saving, setSaving] = useState(false); const [error, setError] = useState('')
  const text = (key: keyof AdminModelPayload, value: string) => setForm(current => ({ ...current, [key]: value }))
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError('')
    const payload = { ...form, api_key: form.api_key || undefined, api_key_env: form.api_key_env || undefined }
    try { await onSave(payload); onClose() } catch (reason) { setError(errorText(reason)) } finally { setSaving(false) }
  }
  return <div className="admin-modal"><form className="admin-modal__card" onSubmit={submit}><header><div><span className="admin-kicker">MODEL CONFIG</span><h2>{item ? '编辑模型' : '新增模型'}</h2></div><button type="button" onClick={onClose} aria-label="关闭模型配置"><X /></button></header>
    <div className="admin-form-grid"><label>供应商<input value={form.provider} onChange={e => text('provider', e.target.value)} required /></label><label>显示名称<input value={form.display_name} onChange={e => text('display_name', e.target.value)} required /></label><label>模型 ID<input value={form.model_id} onChange={e => text('model_id', e.target.value)} required /></label><label>API 类型<select value={form.api_shape} onChange={e => text('api_shape', e.target.value)}><option value="chat_completions">Chat Completions</option><option value="responses">Responses</option><option value="image">Image</option></select></label><label className="wide">Base URL<input value={form.base_url} onChange={e => text('base_url', e.target.value)} required /></label><label className="wide">API Key<input type="password" value={form.api_key || ''} onChange={e => text('api_key', e.target.value)} placeholder={item?.api_key_configured ? '已配置，留空则不修改' : '请输入模型 API Key'} required={!item || !item.api_key_configured && !form.api_key_env} /><small>{item?.api_key_configured ? '已配置密钥；再次填写会覆盖原密钥。' : '密钥会保存到后台模型配置，不会在列表中明文展示。'}</small></label><label className="wide">API Key 环境变量（兼容旧配置）<input value={form.api_key_env || ''} onChange={e => text('api_key_env', e.target.value)} placeholder="例如 GLM_API_KEY，可选" /><small>仅未填写 API Key 时作为兜底读取。</small></label><label className="wide">额外参数 JSON<textarea value={form.extra_body_json || ''} onChange={e => text('extra_body_json', e.target.value)} placeholder='例如 {"thinking":{"type":"disabled"}}' /></label></div>
    <div className="admin-checks">{([['enabled','启用模型'],['support_streaming','流式输出'],['support_tools','工具调用'],['support_image','图片能力']] as const).map(([key,label]) => <label key={key}><input type="checkbox" checked={form[key]} onChange={e => setForm(current => ({...current,[key]:e.target.checked}))} />{label}</label>)}</div>
    {error ? <div className="admin-error">{error}</div> : null}<footer><button type="button" className="admin-quiet" onClick={onClose}>取消</button><button className="admin-primary" disabled={saving}><Save size={16} />{saving ? '保存中…' : '保存配置'}</button></footer></form></div>
}

function ModelsView({ items, onEdit, onNew }: { items: AdminModel[]; onEdit: (item: AdminModel) => void; onNew: () => void }) {
  return <section className="admin-panel"><div className="admin-panel__actions"><div><h2>模型配置</h2><p>配置会写入数据库，调用密钥优先读取后台配置</p></div><button className="admin-primary" onClick={onNew}><Plus size={16} />新增模型</button></div><div className="model-admin-grid">{items.map(item => <article key={item.id}><header><div><span>{item.provider}</span><h3>{item.display_name}</h3></div><i className={item.enabled ? 'on' : ''}>{item.enabled ? '启用' : '停用'}</i></header><code>{item.model_id}</code><p>{item.base_url}</p><div className="model-tags"><span>{item.api_shape}</span>{item.support_streaming && <span>流式</span>}{item.support_tools && <span>工具</span>}{item.support_image && <span>图片</span>}<span>{item.api_key_configured ? 'Key 已配置' : item.api_key_env ? '环境变量 Key' : 'Key 未配置'}</span></div><footer><small>{item.api_key_env || '后台配置密钥'}</small><button className="admin-quiet" onClick={() => onEdit(item)}>编辑</button></footer></article>)}</div></section>
}

function ConversationsView({ items, onOpen }: { items: AdminConversation[]; onOpen: (item: AdminConversation) => void }) {
  return <section className="admin-panel admin-table-wrap"><table><thead><tr><th>会话</th><th>用户</th><th>模式 / 模型</th><th>消息</th><th>更新时间</th><th /></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{item.title || '新会话'}</strong><small>{item.id}</small></td><td>{item.username}</td><td>{item.agent_mode}<small>{item.default_model || '自动选择'}</small></td><td>{item.message_count}<small>{item.run_count} 次运行</small></td><td>{formatDateTime(item.updated_at)}</td><td><button className="admin-icon" onClick={() => onOpen(item)}><ChevronRight size={17} /></button></td></tr>)}</tbody></table></section>
}

function ConversationDrawer({ data, onClose }: { data: AdminConversationDetail | null; onClose: () => void }) {
  return <div className="admin-drawer-backdrop" onClick={onClose}><aside className="admin-drawer" onClick={e => e.stopPropagation()}><header><div><span className="admin-kicker">CONVERSATION</span><h2>{data?.conversation.title || '加载中…'}</h2></div><button onClick={onClose} aria-label="关闭会话详情"><X /></button></header><div className="admin-message-list">{data?.messages.map(message => <article className={`admin-message ${message.role}`} key={message.id}><div><strong>{message.role === 'user' ? '用户' : message.role === 'assistant' ? '助手' : message.role}</strong><span>{message.model || message.agent_name || ''}</span><time>{formatDateTime(message.created_at)}</time></div><p>{message.content}</p></article>)}</div></aside></div>
}

function ExceptionsView({ items, onResolve }: { items: AdminException[]; onResolve: (item: AdminException) => void }) {
  return <section className="admin-panel exception-list">{items.map(item => <details key={item.id}><summary><span className={`exception-level ${item.level}`}>{item.level}</span><div><strong>{item.message}</strong><small>{item.category} · {item.method || 'SYSTEM'} {item.path || ''}</small></div><time>{formatDateTime(item.created_at)}</time><span className={`admin-status ${item.resolved ? 'ok' : 'off'}`}>{item.resolved ? '已处理' : '待处理'}</span></summary><div className="exception-detail"><p>HTTP {item.status_code || '--'} · Code {item.error_code || '--'}</p>{item.detail && <pre>{item.detail}</pre>}{item.traceback && <pre>{item.traceback}</pre>}<button className="admin-quiet" onClick={() => onResolve(item)}>{item.resolved ? '重新打开' : '标记已处理'}</button></div></details>)}{!items.length && <div className="admin-empty">暂无异常记录</div>}</section>
}

export default function AdminApp() {
  const [admin, setAdmin] = useState<AdminUser | null>(null); const [authLoading, setAuthLoading] = useState(true)
  const [section, setSection] = useState<Section>('overview'); const [mobileNav, setMobileNav] = useState(false)
  const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [query, setQuery] = useState('')
  const [overview, setOverview] = useState<AdminOverview | null>(null); const [users, setUsers] = useState<AdminManagedUser[]>([])
  const [tokens, setTokens] = useState<AdminTokenStats | null>(null); const [models, setModels] = useState<AdminModel[]>([])
  const [tokenDateFrom, setTokenDateFrom] = useState(() => dateInput(29)); const [tokenDateTo, setTokenDateTo] = useState(() => dateInput())
  const [conversations, setConversations] = useState<AdminConversation[]>([]); const [exceptions, setExceptions] = useState<AdminException[]>([])
  const [editor, setEditor] = useState<{ open: boolean; item: AdminModel | null }>({ open:false, item:null }); const [conversation, setConversation] = useState<AdminConversationDetail | null>(null)

  useEffect(() => { adminApi.me().then(setAdmin).catch(() => setAdmin(null)).finally(() => setAuthLoading(false)) }, [])
  const load = useCallback(async () => { if (!admin) return; setLoading(true); setError(''); try {
    if (section === 'overview') setOverview(await adminApi.overview())
    if (section === 'users') setUsers(await adminApi.users(query))
    if (section === 'tokens') {
      const exclusiveEnd = new Date(`${tokenDateTo}T00:00:00`)
      exclusiveEnd.setDate(exclusiveEnd.getDate() + 1)
      setTokens(await adminApi.tokenStats(`${tokenDateFrom}T00:00:00`, exclusiveEnd.toISOString()))
    }
    if (section === 'models') setModels(await adminApi.models())
    if (section === 'conversations') setConversations(await adminApi.conversations(query))
    if (section === 'exceptions') setExceptions(await adminApi.exceptions())
  } catch (reason) { setError(errorText(reason)) } finally { setLoading(false) } }, [admin, query, section, tokenDateFrom, tokenDateTo])
  useEffect(() => { void load() }, [load])
  const title = useMemo(() => NAV.find(item => item.id === section)?.label || '', [section])
  if (authLoading) return <div className="admin-boot"><RefreshCw className="spin" />正在验证管理员身份</div>
  if (!admin) return <AdminLogin onLogin={setAdmin} />
  const searchEnabled = section === 'users' || section === 'conversations'
  return <div className="admin-shell">
    <button className={`admin-nav-backdrop ${mobileNav ? 'show' : ''}`} onClick={() => setMobileNav(false)} />
    <aside className={`admin-nav ${mobileNav ? 'show' : ''}`}><header><div className="admin-nav__logo"><ShieldCheck /></div><div><strong>OpenAgent</strong><span>Control Center</span></div><button onClick={() => setMobileNav(false)} aria-label="关闭管理菜单"><X /></button></header><nav>{NAV.map(item => { const Icon=item.icon; return <button className={section===item.id?'active':''} key={item.id} onClick={() => {setSection(item.id);setQuery('');setMobileNav(false)}}><Icon size={18}/>{item.label}</button> })}</nav><footer><div><span>管理员</span><strong>{admin.username}</strong></div><button title="退出" onClick={async()=>{await adminApi.logout();setAdmin(null)}}><LogOut size={18}/></button></footer></aside>
    <main className="admin-main"><header className="admin-topbar"><button className="admin-mobile-menu" onClick={() => setMobileNav(true)} aria-label="打开管理菜单"><Menu /></button><div><span className="admin-kicker">SYSTEM MANAGEMENT</span><h1>{title}</h1></div><div className="admin-topbar__actions">{searchEnabled && <label className="admin-search"><Search size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={section==='users'?'搜索用户名':'搜索会话或用户'}/></label>}<button className="admin-icon" onClick={() => void load()} title="刷新"><RefreshCw className={loading?'spin':''} size={18}/></button></div></header>
      <div className="admin-content">{error && <div className="admin-error">{error}</div>}{section==='overview'&&<Overview data={overview}/>} {section==='users'&&<UsersView items={users} onToggle={async item=>{await adminApi.updateUser(item.id,!item.is_active);await load()}}/>} {section==='tokens'&&<TokensView data={tokens} dateFrom={tokenDateFrom} dateTo={tokenDateTo} onDateFrom={setTokenDateFrom} onDateTo={setTokenDateTo}/>} {section==='models'&&<ModelsView items={models} onNew={()=>setEditor({open:true,item:null})} onEdit={item=>setEditor({open:true,item})}/>} {section==='conversations'&&<ConversationsView items={conversations} onOpen={async item=>{setConversation(await adminApi.conversation(item.id))}}/>} {section==='exceptions'&&<ExceptionsView items={exceptions} onResolve={async item=>{await adminApi.updateException(item.id,!item.resolved);await load()}}/>}</div>
    </main>
    {editor.open && <ModelEditor item={editor.item} onClose={()=>setEditor({open:false,item:null})} onSave={async payload=>{editor.item?await adminApi.updateModel(editor.item.id,payload):await adminApi.createModel(payload);await load()}}/>}
    {conversation && <ConversationDrawer data={conversation} onClose={()=>setConversation(null)}/>} 
  </div>
}
