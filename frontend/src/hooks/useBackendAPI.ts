/**
 * useBackendAPI Hook - Fetch live data from our backend service
 * This is the bridge between DefiLlama data and the frontend
 */
import { useQuery } from '@tanstack/react-query'
import { BACKEND_URL } from '@/lib/contracts'

export interface BackendProtocol {
  protocol: string
  risk_score: number
  anomaly_reasons: string[]
  current_tvl: number
  tvl_change_1h: number
  tvl_change_1d: number
  timestamp: string
}

export interface BackendHealth {
  status: string
  last_update: string
  protocols_monitored: number
  anomalies_detected: number
  oracle_updates: number
  uptime_seconds: number
}

export interface OracleScore {
  score: number
  timestamp: number
  last_updated: string
}

// Fetch live protocol data from backend
export function useBackendProtocols() {
  return useQuery({
    queryKey: ['backend-protocols'],
    queryFn: async (): Promise<BackendProtocol[]> => {
      const response = await fetch(`${BACKEND_URL}/protocols`)
      if (!response.ok) {
        throw new Error(`Backend API error: ${response.status}`)
      }
      const data = await response.json()
      return data.protocols || []
    },
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 15000, // Consider data stale after 15 seconds
  })
}

// Fetch backend health status
export function useBackendHealth() {
  return useQuery({
    queryKey: ['backend-health'],
    queryFn: async (): Promise<BackendHealth> => {
      const response = await fetch(`${BACKEND_URL}/health`)
      if (!response.ok) {
        throw new Error(`Backend health check failed: ${response.status}`)
      }
      return response.json()
    },
    refetchInterval: 10000, // Check health every 10 seconds
  })
}

// Fetch Oracle scores directly from backend
export function useOracleScores() {
  return useQuery({
    queryKey: ['oracle-scores'],
    queryFn: async (): Promise<Record<string, OracleScore>> => {
      const response = await fetch(`${BACKEND_URL}/oracle-scores`)
      if (!response.ok) {
        throw new Error(`Oracle scores fetch failed: ${response.status}`)
      }
      const data = await response.json()
      return data.scores || {}
    },
    refetchInterval: 30000,
  })
}

// Trigger manual system update (for testing)
export async function triggerManualUpdate(): Promise<{ success: boolean; timestamp: string }> {
  const response = await fetch(`${BACKEND_URL}/manual-update`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Manual update failed: ${response.status}`)
  }
  return response.json()
}