'use client'

import { useState, useEffect } from 'react'
import { useCallStore } from '@/lib/stores/callStore'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const DISCLOSURE_TIMEOUT_SECONDS = 30

export default function AIDisclosureTimer({ callSid }: { callSid: string }) {
  const { aiDisclosed, setDisclosed, setOptedOut } = useCallStore()
  const [countdown, setCountdown] = useState(DISCLOSURE_TIMEOUT_SECONDS)
  const [dismissed, setDismissed] = useState(false)
  const [ttsPlaying, setTtsPlaying] = useState(false)

  // Auto-count down
  useEffect(() => {
    if (aiDisclosed || dismissed) return
    if (countdown <= 0) return
    const t = setInterval(() => setCountdown(c => c - 1), 1000)
    return () => clearInterval(t)
  }, [aiDisclosed, dismissed, countdown])

  const handleDisclose = async () => {
    await fetch(`${API_URL}/api/calls/${callSid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai_disclosed: true })
    }).catch(() => {})
    setDisclosed()
    setDismissed(true)
  }

  const handleOptOut = async () => {
    await fetch(`${API_URL}/api/calls/${callSid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ opted_out: true })
    }).catch(() => {})
    setOptedOut()
    setDismissed(true)
  }

  const handlePlayTTS = async () => {
    setTtsPlaying(true)
    try {
      const msg = "Namaste. This call may be assisted by AI to help our counsellor serve you better. You may opt out at any time."
      const res = await fetch(`${API_URL}/api/tts?text=${encodeURIComponent(msg)}&language=hi-IN`, {
        method: 'POST'
      })
      const data = await res.json()
      if (data.audio_base64) {
        const audio = new Audio(`data:audio/wav;base64,${data.audio_base64}`)
        await audio.play()
      }
    } catch (e) {
      console.error('[TTS] Playback failed:', e)
    } finally {
      setTtsPlaying(false)
    }
  }

  if (aiDisclosed || dismissed) return null

  const pct = (countdown / DISCLOSURE_TIMEOUT_SECONDS) * 100
  const urgent = countdown < 10

  return (
    <div className={`fixed bottom-5 right-5 z-50 glass rounded-2xl p-4 w-72 shadow-2xl border fade-in
      ${urgent ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-700/50'}`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-2 h-2 rounded-full ${urgent ? 'bg-amber-400 animate-ping' : 'bg-indigo-400'}`} />
        <span className="text-xs font-semibold text-slate-200">AI Disclosure Required</span>
        <span className={`ml-auto font-mono text-xs font-bold ${urgent ? 'text-amber-400' : 'text-slate-400'}`}>
          {countdown}s
        </span>
      </div>

      {/* Progress ring */}
      <div className="flex justify-center mb-3">
        <svg width="56" height="56" viewBox="0 0 56 56">
          <circle cx="28" cy="28" r="22" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
          <circle
            cx="28" cy="28" r="22" fill="none"
            stroke={urgent ? '#f59e0b' : '#6366f1'}
            strokeWidth="3"
            strokeDasharray={2 * Math.PI * 22}
            strokeDashoffset={2 * Math.PI * 22 * (1 - pct / 100)}
            strokeLinecap="round"
            transform="rotate(-90 28 28)"
            style={{ transition: 'stroke-dashoffset 1s linear' }}
          />
          <text x="28" y="33" textAnchor="middle" fontSize="13" fontWeight="700"
            fill={urgent ? '#f59e0b' : '#818cf8'}>{countdown}</text>
        </svg>
      </div>

      <p className="text-xs text-slate-400 mb-3 text-center leading-relaxed">
        Inform caller that AI is assisting this call.
      </p>

      {/* TTS button */}
      <button
        onClick={handlePlayTTS}
        disabled={ttsPlaying}
        className="w-full mb-2 py-1.5 rounded-lg text-xs font-semibold bg-slate-700/50 border border-slate-600/40 text-slate-300 hover:bg-slate-700 transition-all disabled:opacity-50 cursor-pointer"
      >
        {ttsPlaying ? '🔊 Playing…' : '🔊 Play Disclosure (Hindi)'}
      </button>

      {/* CTA buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleDisclose}
          className="flex-1 py-2 rounded-lg text-xs font-bold bg-indigo-600/50 border border-indigo-500/50 text-indigo-200 hover:bg-indigo-600/70 transition-all cursor-pointer"
        >
          ✓ Disclosed
        </button>
        <button
          onClick={handleOptOut}
          className="flex-1 py-2 rounded-lg text-xs font-semibold bg-slate-700/50 border border-slate-600/40 text-slate-400 hover:bg-slate-700 transition-all cursor-pointer"
        >
          Opt Out
        </button>
      </div>
    </div>
  )
}
