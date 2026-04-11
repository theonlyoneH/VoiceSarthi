import { create } from 'zustand'

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN'

export interface AgentState {
  risk_score: number
  confidence: number
  explanation: string
  flags: string[]
  uncertain: boolean
}

export interface RiskSnapshot {
  timestamp: string
  level: RiskLevel
  score: number
  trigger: string
}

export interface RiskStore {
  level: RiskLevel
  score: number
  confidence: number
  explanation: string
  guidanceText: string
  guidanceId: string
  conflicts: string[]
  agents: Record<string, AgentState>
  history: RiskSnapshot[]
  resourceTriggers: string[]
  guidanceAction: 'pending' | 'accepted' | 'modified' | 'rejected'
  
  setRiskUpdate: (data: any) => void
  setGuidanceAction: (action: 'accepted' | 'modified' | 'rejected', mod?: string) => void
  reset: () => void
}

export const useRiskStore = create<RiskStore>((set, get) => ({
  level: 'UNKNOWN',
  score: 0,
  confidence: 0,
  explanation: '',
  guidanceText: '',
  guidanceId: '',
  conflicts: [],
  agents: {},
  history: [],
  resourceTriggers: [],
  guidanceAction: 'pending',

  setRiskUpdate: (data) => set(state => ({
    level: data.risk_level || 'UNKNOWN',
    score: data.risk_score || 0,
    confidence: data.confidence || 0,
    explanation: data.explanation || '',
    guidanceText: data.guidance_text || '',
    guidanceId: data.guidance_id || '',
    conflicts: data.conflicts || [],
    agents: data.agents_summary || {},
    resourceTriggers: data.resource_triggers || [],
    guidanceAction: 'pending',
    history: [
      ...state.history.slice(-19),
      {
        timestamp: new Date().toISOString(),
        level: data.risk_level || 'UNKNOWN',
        score: data.risk_score || 0,
        trigger: (data.explanation || '').split(' | ')[0] || ''
      }
    ]
  })),

  setGuidanceAction: (action, mod) => set({ guidanceAction: action }),

  reset: () => set({
    level: 'UNKNOWN', score: 0, confidence: 0,
    explanation: '', guidanceText: '', guidanceId: '',
    conflicts: [], agents: {}, history: [], resourceTriggers: [],
    guidanceAction: 'pending'
  })
}))
