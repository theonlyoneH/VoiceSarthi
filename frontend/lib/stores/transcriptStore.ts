import { create } from 'zustand'

export interface TranscriptSegment {
  text: string
  ts: string
  lang: string
  uncertain: boolean
}

export interface TranscriptStore {
  segments: TranscriptSegment[]
  addSegment: (seg: TranscriptSegment) => void
  reset: () => void
}

export const useTranscriptStore = create<TranscriptStore>((set) => ({
  segments: [],

  addSegment: (seg) =>
    set((state) => ({
      segments: [...state.segments.slice(-40), seg],
    })),

  reset: () => set({ segments: [] }),
}))
