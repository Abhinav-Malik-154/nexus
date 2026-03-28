'use client'

import { useMemo } from 'react'
import { PageLayout, PageHeader } from '@/components/layout'
import { Card, Badge, LiveIndicator, LoadingState } from '@/components/ui'
import { useProtocols } from '@/hooks/useProtocols'
import { formatTVL, formatTimestamp } from '@/lib/theme'

export default function AlertsPage() {
  const { protocols, loading, lastUpdate } = useProtocols({ minRisk: 55, limit: 50 })
  const timestamp = Date.now()

  const alerts = useMemo(() => {
    return protocols.map(p => ({
      id: p.id,
      timestamp,
      severity: p.riskLevel,
      protocol: p.name,
      category: p.category,
      message: `${p.name} risk score: ${p.riskScore.toFixed(0)}% - ${p.riskLevel} risk level`,
      tvl: p.tvl,
      change: p.change1d,
    })).sort((a, b) => {
      const severityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
      return severityOrder[a.severity] - severityOrder[b.severity]
    })
  }, [protocols, timestamp])

  const stats = useMemo(() => ({
    total: alerts.length,
    critical: alerts.filter(a => a.severity === 'CRITICAL').length,
    high: alerts.filter(a => a.severity === 'HIGH').length,
  }), [alerts])

  return (
    <PageLayout>
      <PageHeader
        title="Risk Alerts"
        subtitle="Real-time notifications for high-risk protocols"
        status={<LiveIndicator />}
      />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <Card className="text-center py-4">
            <p className="text-3xl font-bold font-mono text-[#e2e8f0]">{stats.total}</p>
            <p className="text-[#64748b] text-xs uppercase">Total Alerts</p>
          </Card>
          <Card variant="danger" className="text-center py-4">
            <p className="text-3xl font-bold font-mono text-red-400">{stats.critical}</p>
            <p className="text-[#64748b] text-xs uppercase">Critical</p>
          </Card>
          <Card variant="warning" className="text-center py-4">
            <p className="text-3xl font-bold font-mono text-orange-400">{stats.high}</p>
            <p className="text-[#64748b] text-xs uppercase">High Risk</p>
          </Card>
        </div>

        {/* Alert Feed */}
        {loading ? (
          <LoadingState message="Loading alerts..." />
        ) : alerts.length === 0 ? (
          <Card className="text-center py-12">
            <div className="text-[#00ff9d] text-4xl mb-4">✓</div>
            <h3 className="text-[#e2e8f0] font-mono font-semibold mb-2">All Clear</h3>
            <p className="text-[#64748b] text-sm">No high-risk alerts at this time</p>
          </Card>
        ) : (
          <div className="space-y-4">
            {alerts.map(alert => (
              <Card
                key={alert.id}
                variant={alert.severity === 'CRITICAL' ? 'danger' : alert.severity === 'HIGH' ? 'warning' : 'default'}
                glow={alert.severity === 'CRITICAL'}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Badge
                        variant={alert.severity === 'CRITICAL' ? 'danger' : 'warning'}
                        pulse={alert.severity === 'CRITICAL'}
                      >
                        {alert.severity}
                      </Badge>
                      <span className="text-[#e2e8f0] font-medium">{alert.protocol}</span>
                      <span className="text-[#64748b] text-sm">{alert.category}</span>
                    </div>
                    <p className="text-[#e2e8f0] text-sm mb-2">{alert.message}</p>
                    <div className="flex items-center gap-4 text-xs text-[#64748b]">
                      <span>TVL: {formatTVL(alert.tvl)}</span>
                      <span>24h: {alert.change >= 0 ? '+' : ''}{alert.change.toFixed(1)}%</span>
                      <span>Just now</span>
                    </div>
                  </div>
                  <button className="text-[#7c3aed] hover:text-white text-sm font-mono transition-colors">
                    View →
                  </button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {lastUpdate && (
          <p className="text-center text-[#475569] text-xs mt-8">
            Last updated: {formatTimestamp(Math.floor(lastUpdate.getTime() / 1000))}
          </p>
        )}
      </div>
    </PageLayout>
  )
}
