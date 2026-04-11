'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Login failed')
      } else {
        localStorage.setItem('vf_token', data.access_token)
        localStorage.setItem('vf_operator', JSON.stringify(data.operator))
        if (data.operator.role === 'supervisor') {
          router.push('/supervisor')
        } else {
          router.push('/operator/queue')
        }
      }
    } catch (e) {
      setError('Could not connect to server')
    }
    setLoading(false)
  }

  const demoLogin = (email: string) => {
    setEmail(email)
    setPassword('demo123')
  }

  return (
    <div className="min-h-screen bg-[#0A0B0F] flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white font-bold text-lg mx-auto mb-4">VF</div>
          <h1 className="text-2xl font-bold text-white">VoiceForward</h1>
          <p className="text-slate-500 text-sm mt-1">AI Copilot for Crisis Helplines</p>
        </div>

        {/* Login form */}
        <form onSubmit={handleLogin} className="glass rounded-2xl p-6 space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50 placeholder:text-slate-600 transition-colors"
              placeholder="operator@helpline.org"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50 placeholder:text-slate-600 transition-colors"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 border border-indigo-500/50 text-white rounded-xl font-semibold text-sm transition-all disabled:opacity-50 cursor-pointer"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* Demo accounts */}
        <div className="mt-4 glass rounded-2xl p-4">
          <p className="text-xs text-slate-500 mb-3 font-semibold">Demo accounts (password: demo123)</p>
          <div className="space-y-2">
            {[
              { label: 'Priya Sharma · Operator (Senior)', email: 'priya@demo.com', role: 'operator' },
              { label: 'Dr. Lakshmi Nair · Supervisor', email: 'supervisor@demo.com', role: 'supervisor' },
            ].map(a => (
              <button
                key={a.email}
                onClick={() => demoLogin(a.email)}
                className="w-full text-left px-3 py-2.5 bg-slate-800/50 border border-slate-700/30 rounded-xl hover:border-slate-600/50 transition-all group"
              >
                <div className="text-xs font-semibold text-slate-300 group-hover:text-slate-200">{a.label}</div>
                <div className="text-[10px] text-slate-600 font-mono">{a.email}</div>
              </button>
            ))}
          </div>
        </div>

        <p className="text-center text-xs text-slate-700 mt-6">
          DPDPA 2023 compliant · Human-first design
        </p>
      </div>
    </div>
  )
}
