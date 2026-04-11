'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const RISK_COLOR: Record<string, string> = {
  CRITICAL: 'text-red-400', HIGH: 'text-orange-400',
  MEDIUM: 'text-amber-400', LOW: 'text-green-400', UNKNOWN: 'text-slate-500'
}

interface Suggestion {
  id: string
  timestamp: string
  suggestion_text: string
  risk_level: string
  risk_score: number
  confidence: number
  operator_action?: string
  reasoning_chain: any
}

export default function AuditReplay({ params }: { params: Promise<{ callSid: string }> }) {
  const { callSid } = use(params)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [timeline, setTimeline] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Suggestion | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [rep, tl] = await Promise.all([
          fetch(`${API_URL}/api/calls/${callSid}/replay`, {
            headers: { Authorization: 'Bearer demo_token' }
          }).then(r => r.json()),
          fetch(`${API_URL}/api/calls/${callSid}/risk-timeline`, {
            headers: { Authorization: 'Bearer demo_token' }
          }).then(r => r.json())
        ])
        setSuggestions(rep.suggestions || [])
        setTimeline(tl.timeline || [])
      } catch (e) {
        console.error('[Replay] Load failed:', e)
      }
      setLoading(false)
    }
    load()
  }, [callSid])

  return (
    <div className="min-h-screen bg-[#0A0B0F] p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/supervisor" className="text-slate-500 hover:text-slate-300 text-sm">← Supervisor</Link>
          <h1 className="text-lg font-bold text-slate-200">Audit Replay</h1>
          <span className="font-mono text-xs text-slate-500">{callSid}</span>
        </div>

        {loading ? (
          <div className="space-y-4">
            {Array.from({length:3}).map((_,i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-5">
            {/* Left: suggestion list */}
            <div className="col-span-5 space-y-2 max-h-[80vh] overflow-y-auto pr-1">
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                AI Suggestions ({suggestions.length})
              </h2>
              {suggestions.length === 0 ? (
                <div className="glass rounded-xl p-8 text-center text-slate-600 text-sm">
                  No suggestions recorded yet
                </div>
              ) : (
                suggestions.map((s, i) => (
                  <button
                    key={s.id}
                    onClick={() => setSelected(s)}
                    className={`w-full text-left glass rounded-xl p-4 transition-all hover:border-slate-600/50 cursor-pointer
                      ${selected?.id === s.id ? 'border-indigo-500/40' : ''}`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs font-bold ${RISK_COLOR[s.risk_level]}`}>
                        {s.risk_level} · {s.risk_score}/10
                      </span>
                      <span className="text-[10px] text-slate-600 ml-auto">
                        {new Date(s.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 line-clamp-2">{s.suggestion_text}</p>
                    {s.operator_action && (
                      <span className={`text-[9px] mt-1.5 inline-block px-1.5 py-0.5 rounded-full font-semibold
                        ${s.operator_action === 'accepted' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                          s.operator_action === 'rejected' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                          'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'}`}>
                        {s.operator_action}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>

            {/* Right: detail + timeline */}
            <div className="col-span-7 space-y-4">
              {/* Risk Timeline */}
              <div className="glass rounded-2xl p-5">
                <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Risk Timeline</h2>
                {timeline.length === 0 ? (
                  <p className="text-xs text-slate-600">No timeline data</p>
                ) : (
                  <div className="space-y-2">
                    {timeline.map((t, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <span className="text-[10px] font-mono text-slate-600 w-20 shrink-0">
                          {new Date(t.timestamp).toLocaleTimeString()}
                        </span>
                        <div className={`w-2 h-2 rounded-full mt-1 shrink-0 ${
                          t.risk_level === 'CRITICAL' ? 'bg-red-500' :
                          t.risk_level === 'HIGH' ? 'bg-orange-500' :
                          t.risk_level === 'MEDIUM' ? 'bg-amber-500' : 'bg-green-500'
                        }`} />
                        <div className="flex-1">
                          <span className={`text-xs font-semibold ${RISK_COLOR[t.risk_level]}`}>
                            {t.risk_level} {t.risk_score && `(${t.risk_score}/10)`}
                          </span>
                          {t.trigger && (
                            <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">{t.trigger}</p>
                          )}
                        </div>
                        {t.operator_action && (
                          <span className="text-[9px] text-slate-500 shrink-0">{t.operator_action}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Selected suggestion detail */}
              {selected && (
                <div className="glass rounded-2xl p-5 fade-in">
                  <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Reasoning Chain</h2>
                  <div className="text-sm text-slate-200 mb-4 leading-relaxed">
                    {selected.suggestion_text}
                  </div>
                  <div className="text-xs text-slate-500">
                    <pre className="bg-slate-900/50 rounded-lg p-3 overflow-x-auto text-[11px] text-slate-400">
                      {JSON.stringify(selected.reasoning_chain, null, 2)}
                    </pre>
                  </div>
                  <div className="flex gap-3 mt-3 text-[11px] text-slate-500">
                    <span>Confidence: {Math.round(selected.confidence * 100)}%</span>
                    <span>Model: {(selected.reasoning_chain as any)?.model_version || 'v1'}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
