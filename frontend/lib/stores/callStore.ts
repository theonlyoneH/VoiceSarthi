import { create } from 'zustand'

export interface CallStore {
  callSid: string | null
  state: string
  startedAt: Date | null
  callerLanguage: string
  priorityTier: string
  aiDisclosed: boolean
  optedOut: boolean
  shadowMode: boolean
  location: { city: string; lat: number; lng: number } | null
  durationSeconds: number

  setCall: (data: any) => void
  setDisclosed: () => void
  setOptedOut: () => void
  setLocation: (loc: { city: string; lat: number; lng: number }) => void
  tick: () => void
  reset: () => void
}

export const useCallStore = create<CallStore>((set, get) => ({
  callSid: null,
  state: 'idle',
  startedAt: null,
  callerLanguage: 'en',
  priorityTier: 'P2',
  aiDisclosed: false,
  optedOut: false,
  shadowMode: false,
  location: null,
  durationSeconds: 0,

  setCall: (data) => set({
    callSid: data.call_sid,
    state: data.state || 'active',
    startedAt: data.started_at ? new Date(data.started_at) : new Date(),
    callerLanguage: data.language_primary || 'en',
    priorityTier: data.priority_tier || 'P2',
    aiDisclosed: data.ai_disclosed || false,
    optedOut: data.opted_out || false,
    shadowMode: data.shadow_mode || false,
  }),

  setDisclosed: () => set({ aiDisclosed: true }),
  setOptedOut: () => set({ optedOut: true, shadowMode: true }),
  setLocation: (loc) => set({ location: loc }),

  tick: () => set(state => ({
    durationSeconds: state.startedAt
      ? Math.floor((Date.now() - state.startedAt.getTime()) / 1000)
      : 0
  })),

  reset: () => set({
    callSid: null, state: 'idle', startedAt: null,
    callerLanguage: 'en', priorityTier: 'P2', aiDisclosed: false,
    optedOut: false, shadowMode: false, location: null, durationSeconds: 0
  })
}))
