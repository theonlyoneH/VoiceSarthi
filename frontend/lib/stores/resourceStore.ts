import { create } from 'zustand'

export interface Resource {
  id: string
  name: string
  category: string
  phone: string | null
  address: string | null
  city: string | null
  lat: number | null
  lng: number | null
  distance_km: number | null
  available_24x7: boolean
  hours: string | null
  dispatchable: boolean
  dispatch_type: string | null
  follow_through_rate: number
}

export interface DispatchAction {
  type: string
  resource_id: string | null
  confirmed: boolean
}

export interface ResourceStore {
  resources: Resource[]
  locationDetected: { city: string; lat: number; lng: number } | null
  mapVisible: boolean
  dispatchPending: DispatchAction | null
  
  setResources: (resources: Resource[]) => void
  setLocation: (loc: { city: string; lat: number; lng: number }) => void
  toggleMap: () => void
  setPendingDispatch: (action: DispatchAction | null) => void
}

export const useResourceStore = create<ResourceStore>((set) => ({
  resources: [],
  locationDetected: null,
  mapVisible: false,
  dispatchPending: null,

  setResources: (resources) => set({ resources }),
  setLocation: (loc) => set({ locationDetected: loc }),
  toggleMap: () => set(state => ({ mapVisible: !state.mapVisible })),
  setPendingDispatch: (action) => set({ dispatchPending: action }),
}))
