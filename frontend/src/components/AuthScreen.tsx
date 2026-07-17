import { useCallback, useState, type FormEvent } from 'react'
import { Bot, KeyRound, Loader2, LockKeyhole, RefreshCw, ShieldCheck, UserRound } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import type { AuthResult, CaptchaChallenge } from '../types'

type Props = {
  onAuthenticated: (result: AuthResult) => Promise<void> | void
}

type AuthErrorData = {
  captcha_required?: boolean
  refresh_captcha?: boolean
}

export function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [captchaCode, setCaptchaCode] = useState('')
  const [captcha, setCaptcha] = useState<CaptchaChallenge | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [captchaLoading, setCaptchaLoading] = useState(false)
  const [error, setError] = useState('')

  const refreshCaptcha = useCallback(async () => {
    setCaptchaLoading(true)
    try {
      setCaptcha(await api.getCaptcha())
      setCaptchaCode('')
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '验证码加载失败')
    } finally {
      setCaptchaLoading(false)
    }
  }, [])

  const switchMode = (nextMode: 'login' | 'register') => {
    setMode(nextMode)
    setError('')
    setPassword('')
    setPasswordConfirm('')
    setCaptcha(null)
    setCaptchaCode('')
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting) return
    setError('')

    if (mode === 'register' && password !== passwordConfirm) {
      setError('两次输入的密码不一致')
      return
    }

    setSubmitting(true)
    try {
      const result = mode === 'register'
        ? await api.register({ username, password, password_confirm: passwordConfirm })
        : await api.login({
            username,
            password,
            captcha_id: captcha?.captcha_id,
            captcha_code: captchaCode || undefined,
          })
      await onAuthenticated(result)
    } catch (nextError) {
      if (nextError instanceof ApiError) {
        setError(nextError.message)
        const data = nextError.data as AuthErrorData | undefined
        if (mode === 'login' && data?.captcha_required) {
          await refreshCaptcha()
        }
      } else {
        setError(nextError instanceof Error ? nextError.message : '请求失败，请稍后重试')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-page__glow auth-page__glow--one" />
      <div className="auth-page__glow auth-page__glow--two" />

      <section className="auth-intro">
        <div className="auth-brand"><Bot size={30} /> OpenAgent Studio</div>
        <div className="auth-intro__content">
          <span className="auth-kicker">智能体工作台</span>
          <h1>让每一次智能体协作<br />都有自己的安全空间</h1>
          <p>登录后，你的会话、消息与 Agent 运行记录会按账号隔离保存。</p>
          <div className="auth-points">
            <span><ShieldCheck size={18} /> 本地账号体系</span>
            <span><LockKeyhole size={18} /> 安全密码哈希</span>
            <span><KeyRound size={18} /> HttpOnly 会话</span>
          </div>
        </div>
        <small>安全、专注的智能体协作空间</small>
      </section>

      <main className="auth-panel-wrap">
        <section className="auth-panel">
          <header>
            <div className="auth-panel__icon"><UserRound size={23} /></div>
            <div>
              <span>{mode === 'login' ? '欢迎回来' : '创建账号'}</span>
              <h2>{mode === 'login' ? '登录工作台' : '注册 OpenAgent Studio'}</h2>
            </div>
          </header>

          <div className="auth-tabs" role="tablist">
            <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>登录</button>
            <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')}>注册</button>
          </div>

          <form onSubmit={handleSubmit}>
            <label className="auth-field">
              <span>用户名</span>
              <div><UserRound size={17} /><input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" minLength={mode === 'register' ? 3 : 1} maxLength={32} placeholder="请输入用户名" required autoFocus /></div>
            </label>

            <label className="auth-field">
              <span>密码</span>
              <div><LockKeyhole size={17} /><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : 1} maxLength={128} placeholder={mode === 'register' ? '至少 8 位密码' : '请输入密码'} required /></div>
            </label>

            {mode === 'register' ? (
              <label className="auth-field">
                <span>确认密码</span>
                <div><ShieldCheck size={17} /><input type="password" value={passwordConfirm} onChange={(event) => setPasswordConfirm(event.target.value)} autoComplete="new-password" minLength={8} maxLength={128} placeholder="请再次输入密码" required /></div>
              </label>
            ) : null}

            {mode === 'login' && captcha ? (
              <div className="captcha-field">
                <span>安全验证码</span>
                <div className="captcha-row">
                  <input value={captchaCode} onChange={(event) => setCaptchaCode(event.target.value.toUpperCase())} maxLength={12} placeholder="输入图中字符" required />
                  <button className="captcha-image" type="button" onClick={() => void refreshCaptcha()} title="换一张验证码">
                    {captchaLoading ? <Loader2 className="spin" size={20} /> : <img src={captcha.image_data_uri} alt="登录验证码" />}
                    <RefreshCw size={14} />
                  </button>
                </div>
                <small>密码连续错误多次，需要完成验证码校验。</small>
              </div>
            ) : null}

            {error ? <div className="auth-error" role="alert">{error}</div> : null}

            <button className="auth-submit" type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="spin" size={18} /> : <KeyRound size={18} />}
              {submitting ? '正在处理…' : mode === 'login' ? '登录' : '注册并进入工作台'}
            </button>
          </form>

          <p className="auth-switch">
            {mode === 'login' ? '还没有账号？' : '已经有账号？'}
            <button type="button" onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? '立即注册' : '返回登录'}
            </button>
          </p>
        </section>
      </main>
    </div>
  )
}
