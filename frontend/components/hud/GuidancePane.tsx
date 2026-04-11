'use client'

import { useRiskStore } from '@/lib/stores/riskStore'
import { useCallStore } from '@/lib/stores/callStore'
import { useState, useEffect, useRef, useCallback } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const RISK_STYLES: Record<string, { bg: string; border: string; icon: string; headerColor: string }> = {
  LOW:      { bg: 'bg-green-500/5',  border: 'border-green-500/20',  icon: '🟢', headerColor: 'text-green-400' },
  MEDIUM:   { bg: 'bg-amber-500/5',  border: 'border-amber-500/25',  icon: '🟡', headerColor: 'text-amber-400' },
  HIGH:     { bg: 'bg-orange-500/5', border: 'border-orange-500/30', icon: '🟠', headerColor: 'text-orange-400' },
  CRITICAL: { bg: 'bg-red-500/5',    border: 'border-red-500/35',    icon: '🔴', headerColor: 'text-red-400' },
  UNKNOWN:  { bg: 'bg-slate-700/20', border: 'border-slate-700/30',  icon: '⚪', headerColor: 'text-slate-500' },
}

export default function GuidancePane({ callSid }: { callSid: string }) {
  const { level, guidanceText, guidanceId, setGuidanceAction, guidanceAction } = useRiskStore()
  const { aiDisclosed } = useCallStore()
  const [showModifyInput, setShowModifyInput] = useState(false)
  const [modText, setModText] = useState('')
  const [prevGuidanceId, setPrevGuidanceId] = useState('')
  const style = RISK_STYLES[level] || RISK_STYLES.UNKNOWN
  const paneRef = useRef<HTMLDivElement>(null)

  // Animate on new guidance
  useEffect(() => {
    if (guidanceId && guidanceId !== prevGuidanceId) {
      setPrevGuidanceId(guidanceId)
      setShowModifyInput(false)
      setModText('')
      if (paneRef.current) {
        paneRef.current.classList.remove('guidance-pop')
        void paneRef.current.offsetWidth // reflow
        paneRef.current.classList.add('guidance-pop')
      }
    }
  }, [guidanceId, prevGuidanceId])

  // Keyboard shortcuts: A=accept, M=modify, R=reject
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'a' || e.key === 'A') handleAction('accepted')
      if (e.key === 'm' || e.key === 'M') setShowModifyInput(v => !v)
      if (e.key === 'r' || e.key === 'R') handleAction('rejected')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [guidanceId])

  const handleAction = async (action: 'accepted' | 'modified' | 'rejected', mod?: string) => {
    setGuidanceAction(action, mod)
    if (!guidanceId) return
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          suggestion_id: guidanceId,
          action,
          modification_text: mod || null
        })
      })
    } catch (e) {
      console.error('[Feedback] Failed to record:', e)
    }
    if (action === 'modified') setShowModifyInput(false)
  }

  const isActed = guidanceAction !== 'pending'

  return (
    <div ref={paneRef} className={`glass rounded-2xl p-4 flex flex-col gap-3 border ${style.border} ${style.bg}`}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-base">{style.icon}</span>
        <span className={`text-xs font-bold uppercase tracking-wider ${style.headerColor}`}>
          AI Guidance
        </span>
        {level !== 'UNKNOWN' && (
          <span className="ml-auto">
            <span className="ai-chip">
              <span className="ai-live-dot" />
              LIVE
            </span>
          </span>
        )}
      </div>

      {/* Guidance text */}
      {!aiDisclosed ? (
        <div className="text-xs text-amber-500/80 bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
          ⚠️ AI assistance not yet disclosed to caller. Please disclose before using guidance.
        </div>
      ) : (
        <div className="guidance-text text-sm leading-relaxed text-slate-200 min-h-[60px]">
          {guidanceText || (
            <span className="text-slate-500 italic">
              Waiting for caller signal…
            </span>
          )}
        </div>
      )}

      {/* A/M/R Buttons */}
      {aiDisclosed && guidanceText && (
        <div className="space-y-2">
          {!isActed ? (
            <div className="flex gap-2">
              <button
                onClick={() => handleAction('accepted')}
                className="btn-accept flex-1 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
              >
                ✓ Accept
                <span className="kbd">A</span>
              </button>
              <button
                onClick={() => setShowModifyInput(v => !v)}
                className="btn-modify flex-1 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
              >
                ✏️ Modify
                <span className="kbd">M</span>
              </button>
              <button
                onClick={() => handleAction('rejected')}
                className="btn-reject flex-1 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
              >
                ✗ Reject
                <span className="kbd">R</span>
              </button>
            </div>
          ) : (
            <div className={`text-center text-xs py-2 rounded-lg font-semibold
              ${guidanceAction === 'accepted' ? 'text-green-400 bg-green-500/10' :
                guidanceAction === 'rejected' ? 'text-red-400 bg-red-500/10' :
                'text-indigo-400 bg-indigo-500/10'}`}>
              {guidanceAction === 'accepted' ? '✓ Guidance accepted' :
               guidanceAction === 'rejected' ? '✗ Guidance rejected' :
               '✏️ Guidance modified'}
            </div>
          )}

          {/* Modify input */}
          {showModifyInput && !isActed && (
            <div className="flex gap-2 fade-in">
              <textarea
                className="flex-1 bg-slate-800/60 border border-slate-700/50 rounded-lg text-xs text-slate-200 p-2 resize-none focus:outline-none focus:border-indigo-500/50 placeholder:text-slate-600"
                rows={2}
                placeholder="Enter your modified guidance…"
                value={modText}
                onChange={e => setModText(e.target.value)}
                autoFocus
              />
              <button
                onClick={() => handleAction('modified', modText)}
                disabled={!modText.trim()}
                className="px-3 py-2 bg-indigo-600/50 border border-indigo-500/40 text-indigo-300 rounded-lg text-xs font-semibold disabled:opacity-40 cursor-pointer"
              >
                Save
              </button>
            </div>
          )}
        </div>
      )}

      {/* Kbd hint */}
      <div className="text-[10px] text-slate-600 flex items-center gap-3">
        <span>Shortcuts:</span>
        <span><span className="kbd">A</span> Accept</span>
        <span><span className="kbd">M</span> Modify</span>
        <span><span className="kbd">R</span> Reject</span>
      </div>
    </div>
  )
}
