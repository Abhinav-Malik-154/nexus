'use client'

import { useState, useMemo } from 'react'
import { PageLayout, PageHeader } from '@/components/layout'
import { Card, CardHeader, CardTitle, CardContent, Tabs, Button, Badge, LiveIndicator } from '@/components/ui'
import { ProtocolTable, ProtocolCard, ModelMetricsDisplay } from '@/components/dashboard/protocols'
import { useProtocols } from '@/hooks/useProtocols'
import { formatTVL, cn } from '@/lib/theme'
import type { Protocol } from '@/types'

const ATTACK_VECTORS = [
  { name: 'Flash Loan', desc: 'Uncollateralized loans used to manipulate markets', freq: 'Monthly', prevention: ['Oracle diversification', 'Transaction delays'] },
  { name: 'Oracle Manipulation', desc: 'Price feed manipulation for arbitrage', freq: 'Weekly', prevention: ['Multiple oracles', 'TWAP pricing'] },
  { name: 'Bridge Exploits', desc: 'Cross-chain vulnerabilities', freq: 'Quarterly', prevention: ['Multi-sig validation', 'Withdrawal delays'] },
  { name: 'Governance Attacks', desc: 'Malicious proposals or vote manipulation', freq: 'Rare', prevention: ['Vote delegation limits', 'Timelocks'] },
] as const

type TabId = 'protocols' | 'attacks' | 'model'

export default function IntelligencePage() {
  const [tab, setTab] = useState<TabId>('protocols')
  const [riskFilter, setRiskFilter] = useState<string>('all')
  const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null)

  const { protocols, loading, error, stats, modelMetrics, refetch, lastUpdate } = useProtocols({
    limit: 100,
    minTvl: 1_000_000,
  })

  const filteredProtocols = useMemo(() => {
    if (riskFilter === 'all') return protocols
    return protocols.filter(p => p.riskLevel === riskFilter)
  }, [protocols, riskFilter])

  const tabs = [
    { id: 'protocols' as TabId, label: 'Protocols', count: protocols.length },
    { id: 'attacks' as TabId, label: 'Attack Vectors' },
    { id: 'model' as TabId, label: 'Model Info' },
  ]

  return (
    <PageLayout>
      <PageHeader
        title="Risk Intelligence"
        subtitle="Real-time protocol risk analysis and threat monitoring"
        status={<LiveIndicator />}
        actions={
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            ↻ Refresh
          </Button>
        }
      />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          {[
            { label: 'Total', value: stats.total, color: 'text-[#06b6d4]' },
            { label: 'Low Risk', value: protocols.filter(p => p.riskLevel === 'LOW').length, color: 'text-[#00ff9d]' },
            { label: 'Medium', value: protocols.filter(p => p.riskLevel === 'MEDIUM').length, color: 'text-amber-400' },
            { label: 'High', value: protocols.filter(p => p.riskLevel === 'HIGH').length, color: 'text-orange-400' },
            { label: 'Critical', value: stats.criticalCount, color: 'text-red-400' },
          ].map(s => (
            <Card key={s.label} className="text-center py-3">
              <p className={cn('text-2xl font-bold font-mono', s.color)}>{s.value}</p>
              <p className="text-[#64748b] text-xs uppercase">{s.label}</p>
            </Card>
          ))}
        </div>

        {/* Tabs */}
        <Tabs tabs={tabs} activeTab={tab} onTabChange={setTab} className="mb-6" />

        {/* Tab Content */}
        {tab === 'protocols' && (
          <div className="space-y-6">
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[#64748b] text-sm">Filter:</span>
              {['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(f => (
                <Button
                  key={f}
                  variant={riskFilter === f ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => setRiskFilter(f)}
                >
                  {f === 'all' ? 'All' : f}
                </Button>
              ))}
            </div>

            {/* Protocol Table */}
            <Card>
              <ProtocolTable
                protocols={filteredProtocols}
                loading={loading}
                error={error}
                onSelect={setSelectedProtocol}
              />
            </Card>

            {/* Last Update */}
            {lastUpdate && (
              <p className="text-[#475569] text-xs text-center">
                Last updated: {lastUpdate.toLocaleTimeString()}
              </p>
            )}
          </div>
        )}

        {tab === 'attacks' && (
          <div className="grid md:grid-cols-2 gap-6">
            {ATTACK_VECTORS.map(attack => (
              <Card key={attack.name} className="hover:border-[#7c3aed]/50 transition-all">
                <CardHeader>
                  <CardTitle>{attack.name}</CardTitle>
                  <Badge variant="warning">{attack.freq}</Badge>
                </CardHeader>
                <CardContent>
                  <p className="text-[#64748b] text-sm mb-4">{attack.desc}</p>
                  <div>
                    <p className="text-[#64748b] text-xs uppercase mb-2">Prevention</p>
                    <ul className="space-y-1">
                      {attack.prevention.map(p => (
                        <li key={p} className="text-[#e2e8f0] text-sm flex items-center gap-2">
                          <span className="text-[#00ff9d]">✓</span> {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {tab === 'model' && (
          <div className="max-w-2xl mx-auto space-y-8">
            <ModelMetricsDisplay metrics={modelMetrics} loading={loading} />
            
            <Card>
              <CardHeader>
                <CardTitle>Model Architecture</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-[#0a0a0a] border border-[#1a1a2e]">
                    <p className="text-[#64748b] text-xs uppercase mb-1">Architecture</p>
                    <p className="text-[#e2e8f0] font-mono">MLP with Residual Blocks</p>
                  </div>
                  <div className="p-3 bg-[#0a0a0a] border border-[#1a1a2e]">
                    <p className="text-[#64748b] text-xs uppercase mb-1">Features</p>
                    <p className="text-[#e2e8f0] font-mono">14 risk indicators</p>
                  </div>
                  <div className="p-3 bg-[#0a0a0a] border border-[#1a1a2e]">
                    <p className="text-[#64748b] text-xs uppercase mb-1">Training Data</p>
                    <p className="text-[#e2e8f0] font-mono">5,000 samples</p>
                  </div>
                  <div className="p-3 bg-[#0a0a0a] border border-[#1a1a2e]">
                    <p className="text-[#64748b] text-xs uppercase mb-1">Loss Function</p>
                    <p className="text-[#e2e8f0] font-mono">Focal Loss (γ=2.0)</p>
                  </div>
                </div>
                
                <div className="pt-4 border-t border-[#1a1a2e]">
                  <p className="text-[#64748b] text-xs">
                    The model is trained on historical protocol data with labels indicating whether an exploit occurred within 30 days. 
                    High recall (71%) means we catch most exploits, but precision (21%) means many false positives.
                    This is intentional — better safe than sorry in DeFi.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Protocol Detail Modal (simplified) */}
      {selectedProtocol && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50" onClick={() => setSelectedProtocol(null)}>
          <div className="max-w-lg w-full" onClick={e => e.stopPropagation()}>
            <Card>
              <CardHeader>
                <CardTitle>{selectedProtocol.name}</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setSelectedProtocol(null)}>×</Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <ProtocolCard protocol={selectedProtocol} />
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-[#64748b] text-xs uppercase">Category</p>
                    <p className="text-[#e2e8f0]">{selectedProtocol.category}</p>
                  </div>
                  <div>
                    <p className="text-[#64748b] text-xs uppercase">Chains</p>
                    <p className="text-[#e2e8f0]">{selectedProtocol.chains.slice(0, 3).join(', ')}{selectedProtocol.chains.length > 3 ? '...' : ''}</p>
                  </div>
                </div>
                <Button variant="primary" className="w-full" onClick={() => window.open(`https://defillama.com/protocol/${selectedProtocol.slug}`, '_blank')}>
                  View on DefiLlama →
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
