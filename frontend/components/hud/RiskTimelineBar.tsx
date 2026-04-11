'use client'

import { useRiskStore, RiskSnapshot } from '@/lib/stores/riskStore'
import { useState, useRef } from 'react'

const SCORE_TO_PERCENT = (score: number) => Math.min(100, Math.max(0, score * 10))
const RISK_COLOR: Record<string, string> = {
  LOW: '#22c55e',
  MEDIUM: '#f59e0b',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
  UNKNOWN: '#64748b',
}

function RiskPin({ snap, index, total }: { snap: RiskSnapshot; index: number; total: number }) {
  const [hovered, setHovered] = useState(false)
  const left = total === 1 ? 50 : (index / (total - 1)) * 100
  const color = RISK_COLOR[snap.level] || RISK_COLOR.UNKNOWN

  return (
    <div
      className="absolute"
      style={{ left: `${left}%`, top: '50%', transform: 'translate(-50%, -50%)', zIndex: hovered ? 20 : 10 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="w-3 h-3 rounded-full border-2 border-white cursor-pointer transition-transform hover:scale-150"
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      />
      {hovered && (
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs whitespace-nowrap z-30 shadow-xl">
          <div className="font-semibold" style={{ color }}>{snap.level} · {snap.score}/10</div>
          <div className="text-slate-400 mt-0.5 max-w-[200px] truncate">{snap.trigger}</div>
          <div className="text-slate-600 text-[10px] mt-1">
            {new Date(snap.timestamp).toLocaleTimeString()}
          </div>
        </div>
      )}
    </div>
  )
}

export default function RiskTimelineBar() {
  const { history, level, score } = useRiskStore()
  const cursorPct = SCORE_TO_PERCENT(score)
  const cursorColor = RISK_COLOR[level] || RISK_COLOR.UNKNOWN

  return (
    <div className="px-5 py-3 bg-[#0A0B0F]/60 border-b border-slate-800/40">
      <div className="flex items-center gap-3">
        <span className="text-xs text-slate-500 font-semibold w-20 shrink-0">RISK SCORE</span>

        {/* Timeline gradient bar */}
        <div className="relative flex-1 h-1.5 rounded-full bg-slate-800">
          {/* Gradient fill to current score */}
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
            style={{
              width: `${cursorPct}%`,
              background: `linear-gradient(to right, #22c55e, ${cursorColor})`
            }}
          />

          {/* History pins */}
          <div className="absolute inset-0">
            {history.slice(-15).map((snap, i) => (
              <RiskPin key={`${snap.timestamp}-${i}`} snap={snap} index={i} total={Math.min(history.length, 15)} />
            ))}
          </div>

          {/* Current cursor */}
          <div
            className="absolute top-1/2 w-3.5 h-3.5 rounded-full border-2 border-white transition-all duration-300"
            style={{
              left: `${cursorPct}%`,
              transform: 'translate(-50%, -50%)',
              background: cursorColor,
              boxShadow: `0 0 12px ${cursorColor}`
            }}
          />
        </div>

        {/* Labels */}
        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-600 shrink-0">
          <span>0</span>
          <span className="text-slate-700">────</span>
          <span>10</span>
        </div>

        {/* History count */}
        {history.length > 0 && (
          <span className="text-[10px] text-slate-600 shrink-0">
            {history.length} updates
          </span>
        )}
      </div>
    </div>
  )
}
