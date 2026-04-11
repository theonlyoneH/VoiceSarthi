'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const PRIORITY_COLOR: Record<string, string> = {
  P0: 'text-red-400 bg-red-500/10 border-red-500/30',
  P1: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  P2: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  P3: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
}

interface QueueCall {
  call_sid: string
  priority_tier: string
  queued_at: string
  started_at?: string
  wait_seconds?: number
}

export default function OperatorQueue() {
  const [calls, setCalls] = useState<QueueCall[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_URL}/api/demo/calls`)
        const data = await res.json()
        setCalls(data.calls || [])
      } catch { setCalls([]) }
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-[#0A0B0F] p-6">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm">← Back</Link>
          <h1 className="text-xl font-bold text-slate-200">Operator Queue</h1>
          <span className="ml-auto text-xs text-slate-500">{calls.length} calls</span>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({length: 3}).map((_, i) => (
              <div key={i} className="skeleton h-16 rounded-xl" />
            ))}
          </div>
        ) : calls.length === 0 ? (
          <div className="glass rounded-2xl p-10 text-center">
            <div className="text-3xl mb-3">📭</div>
            <p className="text-slate-500 text-sm">No calls in queue</p>
            <p className="text-xs text-slate-600 mt-2">
              Run <code className="text-indigo-400 bg-slate-900 px-1 rounded">python demo/simulator.py</code> to generate demo calls
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {['P0','P1','P2','P3'].map(tier => {
              const tiercalls = calls.filter(c => c.priority_tier === tier)
              if (tiercalls.length === 0) return null
              return (
                <div key={tier}>
                  <h2 className={`text-xs font-semibold mb-2 px-1 ${PRIORITY_COLOR[tier].split(' ')[0]}`}>
                    {tier} — {tier === 'P0' ? 'CRITICAL' : tier === 'P1' ? 'HIGH' : tier === 'P2' ? 'STANDARD' : 'LOW PRIORITY'}
                  </h2>
                  {tiercalls.map(call => (
                    <Link
                      key={call.call_sid}
                      href={`/operator/${call.call_sid}`}
                      className="glass flex items-center gap-4 p-4 rounded-xl hover:-translate-y-0.5 hover:border-slate-600/50 transition-all mb-2 block"
                    >
                      <span className={`text-xs px-2 py-1 rounded-full border font-bold ${PRIORITY_COLOR[tier]}`}>
                        {tier}
                      </span>
                      <span className="font-mono text-xs text-slate-300 flex-1">{call.call_sid}</span>
                      <span className="text-xs text-slate-500">
                        {new Date(call.queued_at || call.started_at!).toLocaleTimeString()}
                      </span>
                      <span className="text-xs text-indigo-400 font-semibold">→ Answer</span>
                    </Link>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
