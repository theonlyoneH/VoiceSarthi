'use client'

import { use, useEffect, useRef } from 'react'
import { useCallStore } from '@/lib/stores/callStore'
import { useRiskStore } from '@/lib/stores/riskStore'
import { useTranscriptStore } from '@/lib/stores/transcriptStore'
import { useOperatorWebSocket } from '@/lib/ws'
import TopBar from '@/components/hud/TopBar'
import RiskTimelineBar from '@/components/hud/RiskTimelineBar'
import GlassBoxPanel from '@/components/hud/GlassBoxPanel'
import GuidancePane from '@/components/hud/GuidancePane'
import ResourcePanel from '@/components/hud/ResourcePanel'
import AIDisclosureTimer from '@/components/hud/AIDisclosureTimer'

export default function OperatorHUD({ params }: { params: Promise<{ callSid: string }> }) {
  const { callSid } = use(params)
  const { setCall } = useCallStore()
  const { reset: resetRisk } = useRiskStore()
  const { reset: resetTranscript } = useTranscriptStore()

  // Initialize call state
  useEffect(() => {
    setCall({
      call_sid: callSid,
      state: 'active',
      started_at: new Date().toISOString(),
      priority_tier: 'P1',
      ai_disclosed: false,
      opted_out: false,
      shadow_mode: false,
    })
    return () => {
      resetRisk()
      resetTranscript()
    }
  }, [callSid, setCall, resetRisk, resetTranscript])

  // Single WebSocket connection — handles all event types including stt.segment
  const { sendFeedback } = useOperatorWebSocket(callSid)

  return (
    <div className="min-h-screen bg-[#0A0B0F] flex flex-col">
      {/* Sticky top bar */}
      <TopBar callSid={callSid} />

      {/* Risk timeline */}
      <RiskTimelineBar />

      {/* Main grid layout */}
      <div className="flex-1 grid grid-cols-12 gap-4 p-4 h-[calc(100vh-90px)] overflow-hidden">

        {/* Left column: GlassBox agents */}
        <div className="col-span-3 xl:col-span-3 overflow-y-auto pr-1">
          <GlassBoxPanel />
        </div>

        {/* Center column: Guidance + Transcript area */}
        <div className="col-span-5 xl:col-span-6 flex flex-col gap-4 overflow-y-auto">
          <GuidancePane callSid={callSid} />
          <TranscriptFeed />
        </div>

        {/* Right column: Resources */}
        <div className="col-span-4 xl:col-span-3 overflow-y-auto pl-1">
          <ResourcePanel callSid={callSid} />
        </div>
      </div>

      {/* AI Disclosure timer — floating */}
      <AIDisclosureTimer callSid={callSid} />
    </div>
  )
}

// ─── Transcript Feed ─────────────────────────────────────────────────────────
// Reads from transcriptStore which is fed by the single WS connection above.
// NO separate WebSocket is opened here.

function TranscriptFeed() {
  const segments = useTranscriptStore(s => s.segments)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [segments])

  return (
    <div className="glass rounded-2xl p-4 flex-1 flex flex-col min-h-[200px]">
      <div className="flex items-center gap-2 mb-3">
        <div className="ai-live-dot" />
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Live Transcript</span>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {segments.length === 0 ? (
          <p className="text-xs text-slate-600 italic text-center py-6">
            Transcript will appear as caller speaks…
          </p>
        ) : (
          segments.map((t, i) => (
            <div key={i} className="flex gap-2 text-sm fade-in">
              <span className="text-[10px] text-slate-600 font-mono mt-0.5 w-16 shrink-0">{t.ts}</span>
              <span className={`text-[9px] font-mono mt-1 shrink-0 ${t.uncertain ? 'text-amber-500' : 'text-indigo-400'}`}>
                [{t.lang}]{t.uncertain ? '?' : ''}
              </span>
              <span className="text-slate-200 leading-relaxed">{t.text}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
