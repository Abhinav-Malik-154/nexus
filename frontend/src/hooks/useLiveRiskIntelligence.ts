import { useState, useEffect } from 'react'

// Types for live risk intelligence
export interface LiveRiskData {
  protocol: string
  slug: string
  riskScore: number
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  tvl: number
  category: string
  change1d: number
  change7d: number
  timestamp: string
  confidence: number
}

export interface ModelStats {
  precision: number
  recall: number
  f1: number
  auc: number
  protocolsMonitored: number
  lastUpdate: string
  isActive: boolean
}

export interface LiveRiskResponse {
  success: boolean
  data?: {
    risks: LiveRiskData[]
    stats: ModelStats
    totalProtocols: number
    highRiskCount: number
    criticalRiskCount: number
  }
  timestamp: string
  error?: string
  message?: string
}

/**
 * Hook for fetching live risk intelligence from our trained GNN model
 * Connects to /api/live-risks which runs our Python monitoring script
 */
export function useLiveRiskIntelligence(options: {
  limit?: number
  minRisk?: number
  refreshInterval?: number
  autoRefresh?: boolean
} = {}) {
  const {
    limit = 10,
    minRisk = 0,
    refreshInterval = 60000, // 1 minute
    autoRefresh = true
  } = options

  const [data, setData] = useState<LiveRiskResponse['data'] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)

  const fetchData = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      setError(null)

      const url = new URL('/api/live-risks', window.location.origin)
      url.searchParams.set('limit', limit.toString())
      url.searchParams.set('minRisk', minRisk.toString())

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result: LiveRiskResponse = await response.json()

      if (result.success && result.data) {
        setData(result.data)
        setLastFetch(new Date())
      } else {
        throw new Error(result.error || result.message || 'Failed to fetch data')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
      console.error('Live risk intelligence fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  // Initial fetch
  useEffect(() => {
    fetchData()
  }, [limit, minRisk])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      fetchData(false) // Don't show loading on refresh
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, limit, minRisk])

  return {
    data,
    loading,
    error,
    lastFetch,
    refetch: () => fetchData(true),
    // Computed values with fallback to empty arrays if data is null
    highRiskProtocols: data?.risks?.filter(r => r.riskScore >= 70) || [],
    criticalRiskProtocols: data?.risks?.filter(r => r.riskScore >= 80) || [],
    modelStats: data?.stats || {
      precision: 0,
      recall: 0,
      f1: 0,
      auc: 0,
      protocolsMonitored: 0,
      lastUpdate: new Date().toISOString(),
      isActive: false
    },
  }
}

/**
 * Hook for fetching risk data for specific protocols
 */
export function useSpecificProtocolRisks(protocols: string[]) {
  const [data, setData] = useState<LiveRiskData[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProtocols = async () => {
    if (protocols.length === 0) return

    try {
      setLoading(true)
      setError(null)

      const response = await fetch('/api/live-risks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ protocols }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success && result.data) {
        setData(result.data.risks)
      } else {
        throw new Error(result.error || result.message || 'Failed to fetch protocol data')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
      console.error('Specific protocol fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProtocols()
  }, [protocols.join(',')])

  return {
    data,
    loading,
    error,
    refetch: fetchProtocols,
  }
}

/**
 * Utility functions for risk analysis
 */
export function getRiskColor(level: string | number): string {
  if (typeof level === 'number') {
    if (level >= 80) return '#ef4444' // Critical
    if (level >= 70) return '#f59e0b' // High
    if (level >= 50) return '#eab308' // Medium
    return '#00ff9d' // Low
  }

  switch (level) {
    case 'CRITICAL': return '#ef4444'
    case 'HIGH': return '#f59e0b'
    case 'MEDIUM': return '#eab308'
    case 'LOW': return '#00ff9d'
    default: return '#64748b'
  }
}

export function getRiskLevel(score: number): string {
  if (score >= 80) return 'CRITICAL'
  if (score >= 70) return 'HIGH'
  if (score >= 50) return 'MEDIUM'
  return 'LOW'
}

export function formatTVL(tvl: number): string {
  if (tvl > 1e9) return `$${(tvl / 1e9).toFixed(1)}B`
  if (tvl > 1e6) return `$${(tvl / 1e6).toFixed(0)}M`
  if (tvl > 1e3) return `$${(tvl / 1e3).toFixed(0)}K`
  return `$${Math.round(tvl).toLocaleString()}`
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return '#00ff9d'
  if (confidence >= 0.8) return '#eab308'
  if (confidence >= 0.7) return '#f59e0b'
  return '#ef4444'
}

export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60))

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`
  return date.toLocaleDateString()
}