'use client'

import { useMemo } from 'react'
import { Card, CardHeader, CardTitle, CardContent, Badge, RiskBadge, LoadingState, ErrorState, Skeleton } from '@/components/ui'
import { formatTVL, cn } from '@/lib/theme'
import type { Protocol } from '@/types'

// ═══════════════════════════════════════════════════════════════════════════
//                         PROTOCOL TABLE
// ═══════════════════════════════════════════════════════════════════════════

interface ProtocolTableProps {
  protocols: Protocol[]
  loading?: boolean
  error?: Error | null
  onSelect?: (protocol: Protocol) => void
}

export function ProtocolTable({ protocols, loading, error, onSelect }: ProtocolTableProps) {
  if (loading) return <LoadingState message="Fetching protocols..." />
  if (error) return <ErrorState message={error.message} />
  if (!protocols.length) return <div className="text-center py-8 text-[#64748b]">No protocols found</div>

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1a1a2e]">
            <th className="text-left py-3 px-4 text-[#64748b] text-xs font-mono uppercase tracking-wider">Protocol</th>
            <th className="text-right py-3 px-4 text-[#64748b] text-xs font-mono uppercase tracking-wider">TVL</th>
            <th className="text-right py-3 px-4 text-[#64748b] text-xs font-mono uppercase tracking-wider">24h</th>
            <th className="text-right py-3 px-4 text-[#64748b] text-xs font-mono uppercase tracking-wider">Risk</th>
          </tr>
        </thead>
        <tbody>
          {protocols.map(protocol => (
            <ProtocolRow key={protocol.id} protocol={protocol} onClick={onSelect} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface ProtocolRowProps {
  protocol: Protocol
  onClick?: (protocol: Protocol) => void
}

function ProtocolRow({ protocol, onClick }: ProtocolRowProps) {
  const changeColor = protocol.change1d >= 0 ? 'text-emerald-400' : 'text-red-400'
  
  return (
    <tr
      className={cn(
        'border-b border-[#1a1a2e]/50 hover:bg-[#0f0f0f] transition-colors',
        onClick && 'cursor-pointer'
      )}
      onClick={() => onClick?.(protocol)}
    >
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-[#1a1a2e] flex items-center justify-center text-xs font-bold text-[#64748b]">
            {protocol.name.charAt(0)}
          </div>
          <div>
            <div className="text-[#e2e8f0] font-medium">{protocol.name}</div>
            <div className="text-[#64748b] text-xs">{protocol.category}</div>
          </div>
        </div>
      </td>
      <td className="py-3 px-4 text-right">
        <span className="text-[#e2e8f0] font-mono">{formatTVL(protocol.tvl)}</span>
      </td>
      <td className="py-3 px-4 text-right">
        <span className={cn('font-mono', changeColor)}>
          {protocol.change1d >= 0 ? '+' : ''}{protocol.change1d.toFixed(1)}%
        </span>
      </td>
      <td className="py-3 px-4 text-right">
        <RiskBadge score={protocol.riskScore} />
      </td>
    </tr>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                        PROTOCOL CARDS
// ═══════════════════════════════════════════════════════════════════════════

interface ProtocolCardProps {
  protocol: Protocol
  onClick?: () => void
  compact?: boolean
}

export function ProtocolCard({ protocol, onClick, compact }: ProtocolCardProps) {
  const variant = protocol.riskLevel === 'CRITICAL' ? 'danger' 
    : protocol.riskLevel === 'HIGH' ? 'warning' 
    : 'default'

  return (
    <Card 
      variant={variant} 
      glow={protocol.riskLevel === 'CRITICAL'}
      className={cn('cursor-pointer hover:border-[#7c3aed]/50 transition-all', compact && 'p-3')}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded bg-[#1a1a2e] flex items-center justify-center shrink-0">
            <span className="text-[#00ff9d] font-bold">{protocol.name.charAt(0)}</span>
          </div>
          <div className="min-w-0">
            <h4 className="text-[#e2e8f0] font-medium truncate">{protocol.name}</h4>
            <p className="text-[#64748b] text-xs">{protocol.category}</p>
          </div>
        </div>
        <RiskBadge score={protocol.riskScore} />
      </div>
      
      {!compact && (
        <div className="mt-4 grid grid-cols-3 gap-4 pt-4 border-t border-[#1a1a2e]">
          <div>
            <p className="text-[#64748b] text-xs">TVL</p>
            <p className="text-[#e2e8f0] font-mono">{formatTVL(protocol.tvl)}</p>
          </div>
          <div>
            <p className="text-[#64748b] text-xs">24h Change</p>
            <p className={cn('font-mono', protocol.change1d >= 0 ? 'text-emerald-400' : 'text-red-400')}>
              {protocol.change1d >= 0 ? '+' : ''}{protocol.change1d.toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-[#64748b] text-xs">Chains</p>
            <p className="text-[#e2e8f0] font-mono">{protocol.chains.length}</p>
          </div>
        </div>
      )}
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                       HIGH RISK PANEL
// ═══════════════════════════════════════════════════════════════════════════

interface HighRiskPanelProps {
  protocols: Protocol[]
  loading?: boolean
  title?: string
  limit?: number
}

export function HighRiskPanel({ protocols, loading, title = 'High Risk Protocols', limit = 5 }: HighRiskPanelProps) {
  const highRisk = useMemo(() => 
    protocols
      .filter(p => p.riskLevel === 'HIGH' || p.riskLevel === 'CRITICAL')
      .slice(0, limit),
    [protocols, limit]
  )

  return (
    <Card variant="danger" glow>
      <CardHeader>
        <CardTitle className="text-red-400">{title}</CardTitle>
        <Badge variant="danger" pulse>{highRisk.length} alerts</Badge>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-16" />)}
          </div>
        ) : highRisk.length === 0 ? (
          <div className="text-center py-8 text-[#64748b]">No high risk protocols detected</div>
        ) : (
          <div className="space-y-2">
            {highRisk.map(protocol => (
              <ProtocolCard key={protocol.id} protocol={protocol} compact />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                        RISK DISTRIBUTION
// ═══════════════════════════════════════════════════════════════════════════

interface RiskDistributionProps {
  protocols: Protocol[]
  loading?: boolean
}

export function RiskDistribution({ protocols, loading }: RiskDistributionProps) {
  const distribution = useMemo(() => {
    const counts = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
    protocols.forEach(p => counts[p.riskLevel]++)
    const total = protocols.length || 1
    return {
      low: { count: counts.LOW, percent: (counts.LOW / total) * 100 },
      medium: { count: counts.MEDIUM, percent: (counts.MEDIUM / total) * 100 },
      high: { count: counts.HIGH, percent: (counts.HIGH / total) * 100 },
      critical: { count: counts.CRITICAL, percent: (counts.CRITICAL / total) * 100 },
    }
  }, [protocols])

  if (loading) {
    return <Card><Skeleton className="h-24" /></Card>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Risk Distribution</CardTitle>
        <span className="text-[#64748b] text-xs">{protocols.length} protocols</span>
      </CardHeader>
      <CardContent>
        <div className="h-4 flex rounded overflow-hidden bg-[#1a1a2e]">
          <div className="bg-[#00ff9d]" style={{ width: `${distribution.low.percent}%` }} />
          <div className="bg-amber-500" style={{ width: `${distribution.medium.percent}%` }} />
          <div className="bg-orange-500" style={{ width: `${distribution.high.percent}%` }} />
          <div className="bg-red-500" style={{ width: `${distribution.critical.percent}%` }} />
        </div>
        <div className="mt-4 grid grid-cols-4 gap-2 text-center">
          {[
            { label: 'LOW', ...distribution.low, color: 'text-[#00ff9d]' },
            { label: 'MEDIUM', ...distribution.medium, color: 'text-amber-400' },
            { label: 'HIGH', ...distribution.high, color: 'text-orange-400' },
            { label: 'CRITICAL', ...distribution.critical, color: 'text-red-400' },
          ].map(item => (
            <div key={item.label}>
              <p className={cn('text-lg font-bold font-mono', item.color)}>{item.count}</p>
              <p className="text-[#64748b] text-xs">{item.label}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                          MODEL METRICS
// ═══════════════════════════════════════════════════════════════════════════

interface ModelMetricsDisplayProps {
  metrics: {
    precision: number
    recall: number
    f1: number
    aucRoc: number
    version: string
    lastUpdated: string
  }
  loading?: boolean
}

export function ModelMetricsDisplay({ metrics, loading }: ModelMetricsDisplayProps) {
  if (loading) {
    return <Card><Skeleton className="h-32" /></Card>
  }

  const items = [
    { label: 'Recall', value: metrics.recall, desc: 'Catches 71% of exploits', good: true },
    { label: 'AUC-ROC', value: metrics.aucRoc, desc: 'Better than random', good: true },
    { label: 'F1 Score', value: metrics.f1, desc: 'Balanced metric', good: false },
    { label: 'Precision', value: metrics.precision, desc: 'Some false positives', good: false },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Performance</CardTitle>
        <Badge variant="info">{metrics.version}</Badge>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {items.map(item => (
            <div key={item.label} className="p-3 bg-[#0a0a0a] border border-[#1a1a2e]">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[#64748b] text-xs uppercase">{item.label}</span>
                <span className={cn(
                  'text-lg font-bold font-mono',
                  item.good ? 'text-[#00ff9d]' : 'text-amber-400'
                )}>
                  {(item.value * 100).toFixed(1)}%
                </span>
              </div>
              <p className="text-[#475569] text-xs">{item.desc}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-[#475569] text-xs text-center">
          Last updated: {metrics.lastUpdated}
        </p>
      </CardContent>
    </Card>
  )
}
