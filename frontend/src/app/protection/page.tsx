'use client'

import { useState, useEffect, useCallback } from 'react'
import { PageLayout, PageHeader } from '@/components/layout'
import { Card, Button, Badge } from '@/components/ui'

const BACKEND_URL = 'http://localhost:8000'

interface BackendProtocol {
  protocol: string
  risk_score: number
  anomaly_reasons: string[]
  current_tvl: number
  tvl_change_1h: number
  tvl_change_1d: number
  timestamp: string
}

interface BackendHealth {
  status: string
  last_update: string
  protocols_monitored: number
  anomalies_detected: number
  oracle_updates: number
  uptime_seconds: number
}

// Format large numbers
function formatTVL(tvl: number): string {
  if (tvl >= 1e9) return `$${(tvl / 1e9).toFixed(2)}B`
  if (tvl >= 1e6) return `$${(tvl / 1e6).toFixed(2)}M`
  if (tvl >= 1e3) return `$${(tvl / 1e3).toFixed(2)}K`
  return `$${tvl.toFixed(2)}`
}

function getRiskBadge(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 70) return 'danger'
  if (score >= 40) return 'warning'
  return 'success'
}

export default function ProtectionPage() {
  const [protocols, setProtocols] = useState<BackendProtocol[]>([])
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isUpdating, setIsUpdating] = useState(false)
  const [updateMessage, setUpdateMessage] = useState('')

  // Fetch protocols from backend
  const fetchProtocols = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/protocols`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      setProtocols(data.protocols || [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch')
    }
    setIsLoading(false)
  }, [])

  // Fetch health status
  const fetchHealth = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/health`)
      if (response.ok) {
        const data = await response.json()
        setHealth(data)
      }
    } catch {
      // Silent fail for health check
    }
  }, [])

  // Handle manual update
  const handleManualUpdate = async () => {
    setIsUpdating(true)
    setUpdateMessage('')
    try {
      const response = await fetch(`${BACKEND_URL}/manual-update`, { method: 'POST' })
      if (!response.ok) throw new Error('Update failed')
      const result = await response.json()
      setUpdateMessage(`Updated at ${new Date(result.timestamp).toLocaleTimeString()}`)
      fetchProtocols()
      fetchHealth()
    } catch {
      setUpdateMessage('Update failed - is backend running?')
    }
    setIsUpdating(false)
  }

  // Initial fetch and polling
  useEffect(() => {
    fetchProtocols()
    fetchHealth()
    const interval = setInterval(() => {
      fetchProtocols()
      fetchHealth()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchProtocols, fetchHealth])

  return (
    <PageLayout>
      <PageHeader title="Live Protocol Monitoring" subtitle="Real-time risk data from backend service" />
      
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* System Status Card */}
        <Card className="mb-8 border-[#1e293b]">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-white">System Status</h2>
            <Badge variant={health?.status === 'running' ? 'success' : 'danger'}>
              {health?.status || 'OFFLINE'}
            </Badge>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-[#64748b]">Last Update</div>
              <div className="text-white font-mono">
                {health?.last_update ? new Date(health.last_update).toLocaleTimeString() : 'Never'}
              </div>
            </div>
            <div>
              <div className="text-[#64748b]">Protocols Monitored</div>
              <div className="text-[#00ff9d] font-mono">{health?.protocols_monitored || 0}</div>
            </div>
            <div>
              <div className="text-[#64748b]">Anomalies Detected</div>
              <div className="text-yellow-500 font-mono">{health?.anomalies_detected || 0}</div>
            </div>
            <div>
              <div className="text-[#64748b]">Oracle Updates</div>
              <div className="text-blue-400 font-mono">{health?.oracle_updates || 0}</div>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-4">
            <Button 
              variant="secondary" 
              onClick={handleManualUpdate}
              disabled={isUpdating}
            >
              {isUpdating ? 'Updating...' : 'Trigger Manual Update'}
            </Button>
            {updateMessage && (
              <span className="text-sm text-[#64748b]">{updateMessage}</span>
            )}
          </div>
        </Card>

        {/* Error State */}
        {error && (
          <Card className="mb-8 border-red-500/50 bg-red-500/10">
            <div className="text-red-400">
              <strong>Error connecting to backend:</strong> {error}
            </div>
            <div className="text-sm text-[#64748b] mt-2">
              Make sure the backend service is running: <code className="text-[#00ff9d]">cd backend && python server.py</code>
            </div>
          </Card>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="text-center py-12 text-[#64748b]">
            <div className="animate-pulse text-2xl mb-2">◇</div>
            Loading live protocol data...
          </div>
        )}

        {/* Protocol Grid */}
        {protocols && protocols.length > 0 && (
          <>
            <h2 className="text-xl font-bold text-white mb-4">
              Live Protocol Risk Data ({protocols.length} protocols)
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {protocols.map((protocol) => (
                <Card key={protocol.protocol} className="border-[#1e293b] hover:border-[#00ff9d]/30 transition-colors">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-bold text-white capitalize">{protocol.protocol}</h3>
                    <Badge variant={getRiskBadge(protocol.risk_score)}>
                      Risk: {protocol.risk_score.toFixed(0)}
                    </Badge>
                  </div>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">TVL</span>
                      <span className="text-white font-mono">{formatTVL(protocol.current_tvl)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">1h Change</span>
                      <span className={protocol.tvl_change_1h < 0 ? 'text-red-400' : 'text-green-400'}>
                        {protocol.tvl_change_1h.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">24h Change</span>
                      <span className={protocol.tvl_change_1d < 0 ? 'text-red-400' : 'text-green-400'}>
                        {protocol.tvl_change_1d.toFixed(2)}%
                      </span>
                    </div>
                  </div>

                  {/* Anomaly Reasons */}
                  {protocol.anomaly_reasons.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[#1e293b]">
                      <div className="text-xs text-red-400 font-semibold mb-1">⚠️ ANOMALIES DETECTED</div>
                      {protocol.anomaly_reasons.map((reason, i) => (
                        <div key={i} className="text-xs text-[#64748b]">• {reason}</div>
                      ))}
                    </div>
                  )}

                  {/* Set Protection Button */}
                  <div className="mt-4">
                    <Button variant="secondary" className="w-full text-sm">
                      Set Protection Rule
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}

        {/* Empty State */}
        {protocols && protocols.length === 0 && !isLoading && (
          <Card className="text-center py-12">
            <div className="text-4xl mb-4">◇</div>
            <h3 className="text-lg font-bold text-white mb-2">No Protocol Data</h3>
            <p className="text-[#64748b]">
              Backend is running but no protocols fetched yet. Click "Trigger Manual Update" above.
            </p>
          </Card>
        )}

        {/* How It Works */}
        <Card className="mt-8 border-[#1e293b]">
          <h2 className="text-lg font-bold text-white mb-4">How Real-Time Protection Works</h2>
          <div className="text-[#64748b] text-sm space-y-3">
            <div className="flex gap-3">
              <span className="text-[#00ff9d]">1.</span>
              <span>Backend fetches live data from DefiLlama every 10 minutes</span>
            </div>
            <div className="flex gap-3">
              <span className="text-[#00ff9d]">2.</span>
              <span>Anomaly detector analyzes TVL changes, price drops, volume spikes</span>
            </div>
            <div className="flex gap-3">
              <span className="text-[#00ff9d]">3.</span>
              <span>Risk scores are pushed to on-chain Oracle contract</span>
            </div>
            <div className="flex gap-3">
              <span className="text-[#00ff9d]">4.</span>
              <span>When your threshold is exceeded, funds automatically move to your safe address</span>
            </div>
          </div>
        </Card>
      </div>
    </PageLayout>
  )
}
