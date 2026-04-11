'use client'

import { useEffect } from 'react'
import { useRiskStore } from '@/lib/stores/riskStore'
import { useCallStore } from '@/lib/stores/callStore'

const RISK_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  LOW:      { bg: 'bg-green-500/10',  text: 'text-green-400',  border: 'border-green-500/30', label: 'LOW' },
  MEDIUM:   { bg: 'bg-amber-500/10',  text: 'text-amber-400',  border: 'border-amber-500/30', label: 'MEDIUM' },
  HIGH:     { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30', label: 'HIGH' },
  CRITICAL: { bg: 'bg-red-500/10',    text: 'text-red-400',    border: 'border-red-500/40',   label: 'CRITICAL' },
  UNKNOWN:  { bg: 'bg-slate-500/10',  text: 'text-slate-400',  border: 'border-slate-500/30', label: 'WAITING' },
}

const PRIORITY_COLORS: Record<string, string> = {
  P0: 'text-red-400 border-red-500/30 bg-red-500/10',
  P1: 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  P2: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  P3: 'text-slate-400 border-slate-500/30 bg-slate-500/10',
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export default function TopBar({ callSid }: { callSid: string }) {
  const { level, score, guidanceText } = useRiskStore()
  const { priorityTier, callerLanguage, durationSeconds, aiDisclosed, optedOut, tick } = useCallStore()

  // Timer tick
  useEffect(() => {
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [tick])

  const risk = RISK_COLORS[level] || RISK_COLORS.UNKNOWN
  const isCritical = level === 'CRITICAL'

  return (
    <header className="flex items-center justify-between px-5 h-14 border-b border-slate-800/60 bg-[#0A0B0F]/90 backdrop-blur-md z-50 sticky top-0">
      {/* Left: Logo + Call Info */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xs">VF</div>
          <span className="text-slate-300 font-semibold text-sm hidden sm:block">VoiceForward</span>
        </div>
        <div className="h-5 w-px bg-slate-700" />
        {/* Call SID */}
        <div className="flex items-center gap-2">
          <span className="text-slate-500 text-xs font-mono hidden lg:block">{callSid.slice(0, 20)}</span>
          <div className={`risk-badge ${risk.bg} ${risk.text} border ${risk.border} text-xs px-2 py-0.5 font-bold rounded-full ${isCritical ? 'animate-pulse' : ''}`}>
            {isCritical && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping" />}
            {risk.label} · {score}/10
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${PRIORITY_COLORS[priorityTier] || PRIORITY_COLORS.P2}`}>
            {priorityTier}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-mono uppercase">
            {callerLanguage}
          </span>
        </div>
      </div>

      {/* Center: Timer */}
      <div className="flex items-center gap-3">
        <div className="font-mono text-sm text-slate-300">
          {formatDuration(durationSeconds)}
        </div>
        {optedOut && (
          <div className="text-xs px-2 py-0.5 bg-slate-700/50 border border-slate-600/50 rounded-full text-slate-400">
            SHADOW MODE
          </div>
        )}
      </div>

      {/* Right: AI Disclosure + SOS */}
      <div className="flex items-center gap-3">
        <div className="ai-chip hidden sm:flex">
          <span className="ai-live-dot" />
          AI COPILOT
        </div>
        {!aiDisclosed && (
          <span className="text-xs text-amber-500/70 hidden md:block">AI not disclosed</span>
        )}
        <button className="sos-btn">SOS</button>
      </div>
    </header>
  )
}
