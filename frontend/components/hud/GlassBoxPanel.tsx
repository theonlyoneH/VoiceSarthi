'use client'

import { useRiskStore, AgentState } from '@/lib/stores/riskStore'

const AGENT_META: Record<string, { label: string; icon: string; desc: string }> = {
  emotion:   { label: 'Emotion',   icon: '🎙️', desc: 'Audio prosody & energy analysis' },
  ambient:   { label: 'Ambient',   icon: '🔊', desc: 'Background audio classification' },
  narrative: { label: 'Narrative', icon: '📝', desc: 'Language & phrase pattern analysis' },
  language:  { label: 'Language',  icon: '🌐', desc: 'Code-switch & dialect detection' },
  fatigue:   { label: 'Operator',  icon: '😮‍💨', desc: 'Operator fatigue & shift monitor' },
}

const SCORE_COLOR = (score: number) => {
  if (score <= 2) return { bg: 'bg-green-500/10', border: 'border-green-500/20', text: 'text-green-400', fill: '#22c55e' }
  if (score <= 4) return { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400', fill: '#f59e0b' }
  if (score <= 6) return { bg: 'bg-orange-500/10', border: 'border-orange-500/20', text: 'text-orange-400', fill: '#f97316' }
  return { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', fill: '#ef4444' }
}

function AgentScoreRing({ score }: { score: number }) {
  const r = 14
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 10) * circ
  const c = SCORE_COLOR(score)

  return (
    <svg width="36" height="36" viewBox="0 0 36 36" className="shrink-0">
      <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2.5" />
      <circle
        cx="18" cy="18" r={r} fill="none"
        stroke={c.fill} strokeWidth="2.5"
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 18 18)"
        style={{ transition: 'stroke-dashoffset 0.5s ease' }}
      />
      <text x="18" y="22" textAnchor="middle" fontSize="10" fontWeight="700" fill={c.fill}>{score}</text>
    </svg>
  )
}

function AgentCard({ agentId, data }: { agentId: string; data: AgentState }) {
  const meta = AGENT_META[agentId] || { label: agentId, icon: '🤖', desc: '' }
  const c = SCORE_COLOR(data.risk_score)

  return (
    <div className={`agent-card ${c.bg} border ${c.border} p-3 rounded-xl flex items-start gap-3 transition-all duration-300`}>
      <AgentScoreRing score={data.risk_score} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm">{meta.icon}</span>
          <span className="text-xs font-semibold text-slate-200">{meta.label}</span>
          <span className={`ml-auto text-[10px] font-mono ${c.text}`}>
            {Math.round(data.confidence * 100)}%
          </span>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
          {data.explanation || meta.desc}
        </p>
        {data.flags && data.flags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {data.flags.slice(0, 2).map((f, i) => (
              <span key={i} className="text-[9px] px-1.5 py-0.5 bg-slate-700/50 border border-slate-600/30 rounded-full text-slate-400 font-mono truncate max-w-[140px]">
                {f.length > 25 ? f.slice(0, 25) + '…' : f}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="agent-card p-3 rounded-xl">
      <div className="flex items-center gap-3">
        <div className="skeleton w-9 h-9 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-3 w-20 rounded" />
          <div className="skeleton h-2 w-full rounded" />
          <div className="skeleton h-2 w-3/4 rounded" />
        </div>
      </div>
    </div>
  )
}

export default function GlassBoxPanel() {
  const { agents, conflicts, level } = useRiskStore()
  const agentIds = Object.keys(agents)

  return (
    <div className="glass rounded-2xl p-4 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="ai-live-dot" />
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">GlassBox Agents</span>
        </div>
        <span className="text-[10px] text-slate-600 font-mono">{agentIds.length}/5 active</span>
      </div>

      {/* Conflict banner */}
      {conflicts && conflicts.length > 0 && (
        <div className="conflict-banner fade-in">
          <span>⚠️</span>
          <span className="text-xs">
            <strong>Agent Conflict</strong> — Safety-first: highest risk score applied.{' '}
            {conflicts[0].slice(0, 80)}
          </span>
        </div>
      )}

      {/* Agent cards grid */}
      <div className="grid grid-cols-1 gap-2">
        {agentIds.length === 0
          ? Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
          : agentIds.map(id => (
              <AgentCard key={id} agentId={id} data={agents[id]} />
            ))
        }
      </div>

      {/* GlassBox explainer */}
      <div className="text-[10px] text-slate-600 text-center pt-1 border-t border-slate-800/50">
        All reasoning is visible · No black-box decisions
      </div>
    </div>
  )
}
