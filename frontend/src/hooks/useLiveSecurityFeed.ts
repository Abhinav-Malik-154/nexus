'use client'

import { useState, useEffect, useCallback } from 'react'

interface SecurityThreat {
  id: string
  title: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  date: string
  timeAgo: string
  type: string
  source: string
  amount?: string
  protocols?: string[]
  affected?: string[]
  confidence?: number
}

interface SecuritySummary {
  total: number
  critical: number
  high: number
  last_updated: string
}

interface LiveSecurityData {
  threats: SecurityThreat[]
  summary: SecuritySummary
  timestamp: string
}

interface UseLiveSecurityFeedReturn {
  data: LiveSecurityData | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  lastUpdated: Date | null
}

export function useLiveSecurityFeed(refreshInterval = 300000): UseLiveSecurityFeedReturn { // 5 minutes
  const [data, setData] = useState<LiveSecurityData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchSecurityFeed = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/live-security-feed', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store'
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to fetch security feed`)
      }

      const result = await response.json()

      if (result.success) {
        setData(result.data)
        setError(null)
      } else {
        // Use fallback data if available
        if (result.fallback) {
          setData(result.fallback)
        }
        setError(result.error || 'Security feed unavailable')
      }

      setLastUpdated(new Date())
    } catch (err) {
      console.error('Security feed fetch error:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch live security intelligence')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial fetch
  useEffect(() => {
    fetchSecurityFeed()
  }, [fetchSecurityFeed])

  // Auto-refresh interval
  useEffect(() => {
    if (refreshInterval <= 0) return

    const interval = setInterval(fetchSecurityFeed, refreshInterval)
    return () => clearInterval(interval)
  }, [fetchSecurityFeed, refreshInterval])

  const refresh = useCallback(async () => {
    await fetchSecurityFeed()
  }, [fetchSecurityFeed])

  return {
    data,
    loading,
    error,
    refresh,
    lastUpdated
  }
}