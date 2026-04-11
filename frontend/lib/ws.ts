'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useRiskStore } from './stores/riskStore'
import { useCallStore } from './stores/callStore'
import { useResourceStore } from './stores/resourceStore'
import { useTranscriptStore } from './stores/transcriptStore'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
const RECONNECT_DELAY = 2000
const MAX_RECONNECT_ATTEMPTS = 10

export function useOperatorWebSocket(callSid: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCount = useRef(0)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  const setRiskUpdate = useRiskStore(s => s.setRiskUpdate)
  const setCall = useCallStore(s => s.setCall)
  const setLocation = useResourceStore(s => s.setLocation)
  const setResources = useResourceStore(s => s.setResources)
  const addSegment = useTranscriptStore(s => s.addSegment)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(`${WS_URL}/ws/operator/${callSid}`)
    wsRef.current = ws

    ws.onopen = () => {
      console.log(`[WS] Operator connected for call ${callSid}`)
      reconnectCount.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        switch (data.type) {
          case 'meta.risk_update':
            setRiskUpdate(data)
            break
          case 'state_sync':
            if (data.call_sid) setCall(data)
            break
          case 'call.state_change':
            setCall({ ...data, state: data.new_state })
            break
          case 'location.detected':
            if (data.city) setLocation(data)
            break
          case 'resources.updated':
            if (data.resources) setResources(data.resources)
            break
          case 'stt.segment':
            if (data.text) {
              addSegment({
                text: data.text,
                ts: new Date().toLocaleTimeString(),
                lang: data.language_tags?.[0]?.lang?.toUpperCase() || 'EN',
                uncertain: data.uncertain || false,
              })
            }
            break
          case 'stt_degraded':
            console.warn('[STT] Degraded mode — Whisper fallback active')
            break
        }
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('[WS] Error:', error)
    }

    ws.onclose = () => {
      console.log('[WS] Disconnected')
      if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectCount.current++
        const delay = RECONNECT_DELAY * Math.min(reconnectCount.current, 5)
        reconnectTimeout.current = setTimeout(connect, delay)
      }
    }
  }, [callSid, setRiskUpdate, setCall, setLocation, setResources, addSegment])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const sendFeedback = useCallback((
    action: 'accepted' | 'modified' | 'rejected',
    guidanceId: string,
    operatorId: string,
    modificationText?: string
  ) => {
    sendMessage({
      type: 'operator.feedback',
      suggestion_id: guidanceId,
      action,
      operator_id: operatorId,
      modification_text: modificationText || null
    })
  }, [sendMessage])

  return { sendMessage, sendFeedback }
}

export function useSupervisorWebSocket(helplineId: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(`${WS_URL}/ws/supervisor/${helplineId}`)
      wsRef.current = ws

      ws.onopen = () => {
        console.log(`[WS] Supervisor connected for helpline ${helplineId}`)
      }

      ws.onclose = () => {
        reconnectTimeout.current = setTimeout(connect, RECONNECT_DELAY)
      }

      // Return ws for component-level message handling
      return ws
    }

    const ws = connect()
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      wsRef.current?.close()
    }
  }, [helplineId])

  return { wsRef }
}
