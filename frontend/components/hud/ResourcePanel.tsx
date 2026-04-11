'use client'

import { useResourceStore, Resource } from '@/lib/stores/resourceStore'
import { useRiskStore } from '@/lib/stores/riskStore'
import { useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CATEGORY_META: Record<string, { icon: string; label: string; color: string }> = {
  ambulance:    { icon: '🚑', label: 'Ambulance',    color: 'text-red-400' },
  police:       { icon: '👮', label: 'Police',       color: 'text-blue-400' },
  hospital:     { icon: '🏥', label: 'Hospital',     color: 'text-cyan-400' },
  shelter:      { icon: '🏠', label: 'Shelter',      color: 'text-purple-400' },
  mental_health:{ icon: '🧠', label: 'Mental Health',color: 'text-pink-400' },
  helpline:     { icon: '📞', label: 'Helpline',     color: 'text-green-400' },
  ngo:          { icon: '🤝', label: 'NGO',          color: 'text-amber-400' },
  pharmacy:     { icon: '💊', label: 'Pharmacy',     color: 'text-teal-400' },
}

async function dispatchAction(callSid: string, actionType: string, resourceId?: string) {
  const res = await fetch(`${API_URL}/api/dispatch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      call_sid: callSid,
      action_type: actionType,
      resource_id: resourceId || null,
      confirmed: true
    })
  })
  return res.json()
}

function ResourceRow({ resource, callSid }: { resource: Resource; callSid: string }) {
  const meta = CATEGORY_META[resource.category] || { icon: '📍', label: resource.category, color: 'text-slate-400' }
  const [status, setStatus] = useState<'idle' | 'pending' | 'done' | 'error'>('idle')

  async function handleDispatch() {
    setStatus('pending')
    try {
      const result = await dispatchAction(callSid, resource.category === 'ambulance' ? 'ambulance' : 'resource_connect', resource.id)
      setStatus(result.status === 'confirmed' ? 'done' : 'error')
    } catch {
      setStatus('error')
    }
    setTimeout(() => setStatus('idle'), 4000)
  }

  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:border-slate-600/40 hover:bg-slate-800/50 transition-all">
      <span className="text-lg shrink-0">{meta.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-200 truncate">{resource.name}</span>
          {resource.available_24x7 && (
            <span className="text-[9px] px-1 py-0.5 bg-green-500/10 border border-green-500/20 text-green-400 rounded font-semibold shrink-0">24/7</span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {resource.phone && (
            <span className="text-[11px] font-mono text-indigo-400">{resource.phone}</span>
          )}
          {resource.distance_km != null && (
            <span className="text-[10px] text-slate-500">{resource.distance_km}km</span>
          )}
          {resource.city && (
            <span className={`text-[10px] ${meta.color} opacity-70`}>{resource.city}</span>
          )}
        </div>
      </div>

      {resource.dispatchable && (
        <button
          onClick={handleDispatch}
          disabled={status === 'pending' || status === 'done'}
          className={`shrink-0 text-[10px] px-2 py-1.5 rounded-lg font-semibold transition-all cursor-pointer
            ${status === 'done' ? 'bg-green-500/20 border border-green-500/30 text-green-400' :
              status === 'pending' ? 'bg-slate-700/50 border border-slate-600/30 text-slate-400 animate-pulse' :
              status === 'error' ? 'bg-red-500/20 border border-red-500/30 text-red-400' :
              'bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/25'}`}
        >
          {status === 'done' ? '✓ Sent' :
           status === 'pending' ? '…' :
           status === 'error' ? '✗' :
           'Dispatch'}
        </button>
      )}
    </div>
  )
}

export default function ResourcePanel({ callSid }: { callSid: string }) {
  const { resources, setResources, locationDetected } = useResourceStore()
  const { level, resourceTriggers } = useRiskStore()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!level || level === 'UNKNOWN') return

    const fetchResources = async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams({ risk_level: level, limit: '6' })
        if (locationDetected?.city) params.set('city', locationDetected.city)
        const res = await fetch(`${API_URL}/api/resources?${params}`)
        const data = await res.json()
        if (data.resources) setResources(data.resources)
      } catch (e) {
        console.error('[Resources] Fetch failed:', e)
      } finally {
        setLoading(false)
      }
    }

    fetchResources()
  }, [level, locationDetected, setResources])

  return (
    <div className="glass rounded-2xl p-4 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Nearby Resources
        </span>
        <div className="flex items-center gap-2">
          {locationDetected && (
            <span className="text-[10px] text-slate-500 flex items-center gap-1">
              📍 {locationDetected.city}
            </span>
          )}
          {loading && <span className="w-3 h-3 border border-indigo-400 border-t-transparent rounded-full animate-spin" />}
        </div>
      </div>

      {/* Resource list */}
      {resources.length === 0 ? (
        <div className={loading ? 'space-y-2' : 'text-xs text-slate-600 text-center py-4'}>
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton h-12 rounded-lg" />
            ))
          ) : (
            'Resources will appear as call progresses…'
          )}
        </div>
      ) : (
        <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
          {resources.map(r => (
            <ResourceRow key={r.id} resource={r} callSid={callSid} />
          ))}
        </div>
      )}

      {/* Trigger chip */}
      {resourceTriggers.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {resourceTriggers.map(t => (
            <span key={t} className="text-[9px] px-1.5 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-full font-semibold">
              {t.replace('show_', '').replace('_', ' ')}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
