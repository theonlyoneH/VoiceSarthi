'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useSupervisorWebSocket } from '@/lib/ws'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const HELPLINE_ID = '00000000-0000-0000-0000-000000000001'

const RISK_COLOR: Record<string, string> = {
  CRITICAL: 'border-red-500/50 bg-red-500/5',
  HIGH:     'border-orange-500/40 bg-orange-500/5',
  MEDIUM:   'border-amber-500/30 bg-amber-500/5',
  LOW:      'border-green-500/20 bg-green-500/5',
  UNKNOWN:  'border-slate-700/30 bg-slate-800/20',
}

const RISK_TEXT: Record<string, string> = {
  CRITICAL: 'text-red-400', HIGH: 'text-orange-400',
  MEDIUM: 'text-amber-400', LOW: 'text-green-400', UNKNOWN: 'text-slate-500'
}

const PRIORITY_COLOR: Record<string, string> = {
  P0: 'text-red-400', P1: 'text-orange-400', P2: 'text-amber-400', P3: 'text-slate-400'
}

interface ActiveCall {
  call_sid: string
  operator_id?: string
  started_at: string
  priority_tier: string
  final_risk_level: string
  ai_disclosed: boolean
  language_primary: string
}

interface QueueState { p0: number; p1: number; p2: number; p3: number }

function formatAgo(ts: string) {
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`
  return `${Math.floor(diff/3600)}h ago`
}

function CallCard({ call }: { call: ActiveCall }) {
  const risk = call.final_risk_level || 'UNKNOWN'
  const isCritical = risk === 'CRITICAL'

  return (
    <Link href={`/operator/${call.call_sid}`}
      className={`block border rounded-xl p-4 transition-all hover:-translate-y-0.5 cursor-pointer ${RISK_COLOR[risk]} ${isCritical ? 'animate-pulse-subtle' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className={`text-xs font-bold ${RISK_TEXT[risk]}`}>{risk}</span>
            <span className={`text-xs font-semibold ${PRIORITY_COLOR[call.priority_tier]}`}>{call.priority_tier}</span>
            {!call.ai_disclosed && (
              <span className="text-[9px] px-1.5 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-500 rounded-full">
                Undisclosed
              </span>
            )}
          </div>
          <div className="font-mono text-xs text-slate-400">{call.call_sid.slice(0, 28)}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[10px] text-slate-500">{formatAgo(call.started_at)}</div>
          {call.language_primary && (
            <div className="text-[10px] text-indigo-400 font-mono uppercase mt-1">{call.language_primary}</div>
          )}
        </div>
      </div>
      <div className="text-[10px] text-indigo-400/70 mt-2">→ Open HUD</div>
    </Link>
  )
}

function QueueBar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (count / max) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <span className={`text-xs font-bold w-8 ${color}`}>{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${
          label === 'P0' ? 'bg-red-500' : label === 'P1' ? 'bg-orange-500' :
          label === 'P2' ? 'bg-amber-500' : 'bg-slate-500'
        }`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-mono font-bold ${color} w-6 text-right`}>{count}</span>
    </div>
  )
}

export default function SupervisorDashboard() {
  const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([])
  const [queue, setQueue] = useState<QueueState>({ p0: 0, p1: 0, p2: 0, p3: 0 })
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // WS for live updates
  const { wsRef } = useSupervisorWebSocket(HELPLINE_ID)

  useEffect(() => {
    if (!wsRef.current) return
    const ws = wsRef.current
    ws.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'call.risk_update') {
          setActiveCalls(prev => prev.map(c =>
            c.call_sid === data.call_sid
              ? { ...c, final_risk_level: data.risk_level }
              : c
          ))
        } else if (data.type === 'board_sync' || data.active_calls) {
          if (data.active_calls) setActiveCalls(data.active_calls)
          if (data.queue) setQueue(data.queue)
          setLastUpdate(new Date())
        }
      } catch (_) {}
    }
  }, [wsRef])

  const fetchBoard = async () => {
    try {
      const res = await fetch(`${API_URL}/api/supervisor/board`, {
        headers: { 'Authorization': 'Bearer demo_token' }
      })
      if (res.ok) {
        const data = await res.json()
        setActiveCalls(data.active_calls || [])
        setQueue(data.queue || { p0: 0, p1: 0, p2: 0, p3: 0 })
        setLastUpdate(new Date())
      }
    } catch (_) {}
    setLoading(false)
  }

  useEffect(() => {
    fetchBoard()
    const interval = setInterval(fetchBoard, 10000)
    return () => clearInterval(interval)
  }, [])

  // Sort by risk: CRITICAL first
  const riskOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, UNKNOWN: 4 }
  const sorted = [...activeCalls].sort((a, b) => {
    return (riskOrder[a.final_risk_level] ?? 4) - (riskOrder[b.final_risk_level] ?? 4)
  })

  const totalQueue = queue.p0 + queue.p1 + queue.p2 + queue.p3
  const maxQueue = Math.max(totalQueue, 5)

  return (
    <div className="min-h-screen bg-[#0A0B0F]">
      {/* Header */}
      <header className="sticky top-0 z-50 flex items-center justify-between px-6 h-14 border-b border-slate-800/60 bg-[#0A0B0F]/95 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <Link href="/" className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xs">VF</Link>
          <span className="font-semibold text-slate-200">Supervisor Dashboard</span>
          <div className="flex items-center gap-1.5 ml-2">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-slate-500">LIVE</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {lastUpdate && (
            <span className="text-xs text-slate-600">
              Updated {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <Link href="/operator/queue" className="text-xs px-3 py-1.5 bg-slate-800 border border-slate-700/50 rounded-lg text-slate-300 hover:bg-slate-700 transition-all">
            Queue View
          </Link>
        </div>
      </header>

      <div className="p-6 grid grid-cols-12 gap-5">
        {/* Left: Queue panel */}
        <div className="col-span-3">
          <div className="glass rounded-2xl p-5 mb-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Call Queue</h2>
            <div className="space-y-3">
              <QueueBar label="P0" count={queue.p0} max={maxQueue} color="text-red-400" />
              <QueueBar label="P1" count={queue.p1} max={maxQueue} color="text-orange-400" />
              <QueueBar label="P2" count={queue.p2} max={maxQueue} color="text-amber-400" />
              <QueueBar label="P3" count={queue.p3} max={maxQueue} color="text-slate-400" />
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/50 text-xs text-slate-500">
              Total: <span className="text-slate-300 font-semibold">{totalQueue}</span> waiting
            </div>
          </div>

          {/* Stats */}
          <div className="glass rounded-2xl p-4">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Active Calls</h3>
            <div className="text-3xl font-bold text-slate-100">{activeCalls.length}</div>
            <div className="mt-2 space-y-1">
              {['CRITICAL','HIGH','MEDIUM','LOW'].map(risk => {
                const cnt = activeCalls.filter(c => c.final_risk_level === risk).length
                if (cnt === 0) return null
                return (
                  <div key={risk} className="flex justify-between text-xs">
                    <span className={RISK_TEXT[risk]}>{risk}</span>
                    <span className="text-slate-300 font-semibold">{cnt}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Right: Live call cards */}
        <div className="col-span-9">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Live Calls — sorted by risk
            </h2>
          </div>

          {loading ? (
            <div className="grid grid-cols-3 gap-3">
              {Array.from({length:6}).map((_,i) => (
                <div key={i} className="skeleton h-28 rounded-xl" />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="glass rounded-2xl p-12 text-center col-span-3">
              <div className="text-3xl mb-3">📭</div>
              <p className="text-slate-500 text-sm">No active calls</p>
              <p className="text-xs text-slate-600 mt-2">
                Run demo simulator to see live calls appear here
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
              {sorted.map(call => (
                <CallCard key={call.call_sid} call={call} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
