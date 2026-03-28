'use client'

import { useState, useMemo } from 'react'
import { PageLayout, PageHeader } from '@/components/layout'
import { Card, Badge, RiskBadge, LoadingState, LiveIndicator } from '@/components/ui'
import { useProtocols } from '@/hooks/useProtocols'
import { getRiskColor, cn } from '@/lib/theme'
import type { Protocol } from '@/types'

export default function RiskMapPage() {
  const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null)
  const { protocols, loading } = useProtocols({ limit: 50, minTvl: 50_000_000 })

  const categories = useMemo(() => {
    const map = new Map<string, Protocol[]>()
    protocols.forEach(p => {
      if (!map.has(p.category)) map.set(p.category, [])
      map.get(p.category)!.push(p)
    })
    return Array.from(map.entries()).map(([cat, protos]) => ({
      name: cat,
      protocols: protos,
      avgRisk: protos.reduce((sum, p) => sum + p.riskScore, 0) / protos.length,
      count: protos.length,
    })).sort((a, b) => b.avgRisk - a.avgRisk)
  }, [protocols])

  return (
    <PageLayout>
      <PageHeader
        title="Protocol Risk Map"
        subtitle="Interactive visualization of DeFi protocol risk landscape"
        status={<LiveIndicator />}
      />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <LoadingState message="Mapping protocols..." />
        ) : (
          <div className="grid md:grid-cols-3 gap-8">
            {/* Left: Category Map */}
            <div className="md:col-span-2 space-y-4">
              <Card>
                <div className="text-[#64748b] text-xs uppercase mb-4">Risk by Category</div>
                <div className="space-y-3">
                  {categories.map(cat => (
                    <div key={cat.name} className="group">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[#e2e8f0] text-sm font-medium">{cat.name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[#64748b] text-xs">{cat.count} protocols</span>
                          <RiskBadge score={cat.avgRisk} size="sm" />
                        </div>
                      </div>
                      <div className="h-2 bg-[#1a1a2e] rounded overflow-hidden">
                        <div
                          className="h-full transition-all"
                          style={{
                            width: `${cat.avgRisk}%`,
                            backgroundColor: getRiskColor(cat.avgRisk),
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Protocol Grid */}
              <Card>
                <div className="text-[#64748b] text-xs uppercase mb-4">Protocol Network</div>
                <div className="grid grid-cols-4 sm:grid-cols-6 gap-3">
                  {protocols.slice(0, 24).map(protocol => (
                    <button
                      key={protocol.id}
                      onClick={() => setSelectedProtocol(protocol)}
                      className={cn(
                        'aspect-square rounded border-2 transition-all',
                        'flex flex-col items-center justify-center p-2',
                        'hover:scale-110 hover:z-10',
                        selectedProtocol?.id === protocol.id && 'ring-2 ring-[#7c3aed]'
                      )}
                      style={{
                        borderColor: getRiskColor(protocol.riskScore),
                        backgroundColor: `${getRiskColor(protocol.riskScore)}15`,
                      }}
                      title={protocol.name}
                    >
                      <span className="text-lg mb-1">{protocol.name.charAt(0)}</span>
                      <span className="text-[10px] text-center truncate w-full">
                        {protocol.name.split(' ')[0]}
                      </span>
                    </button>
                  ))}
                </div>
              </Card>
            </div>

            {/* Right: Details Panel */}
            <div className="space-y-4">
              {selectedProtocol ? (
                <>
                  <Card>
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-[#e2e8f0] font-medium">{selectedProtocol.name}</h3>
                        <p className="text-[#64748b] text-sm">{selectedProtocol.category}</p>
                      </div>
                      <RiskBadge score={selectedProtocol.riskScore} />
                    </div>
                    
                    <div className="space-y-3 text-sm">
                      <div className="flex justify-between py-2 border-t border-[#1a1a2e]">
                        <span className="text-[#64748b]">TVL</span>
                        <span className="text-[#e2e8f0] font-mono">
                          ${(selectedProtocol.tvl / 1e6).toFixed(0)}M
                        </span>
                      </div>
                      <div className="flex justify-between py-2 border-t border-[#1a1a2e]">
                        <span className="text-[#64748b]">24h Change</span>
                        <span className={cn('font-mono', selectedProtocol.change1d >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {selectedProtocol.change1d >= 0 ? '+' : ''}{selectedProtocol.change1d.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between py-2 border-t border-[#1a1a2e]">
                        <span className="text-[#64748b]">Chains</span>
                        <span className="text-[#e2e8f0]">{selectedProtocol.chains.length}</span>
                      </div>
                      <div className="flex justify-between py-2 border-t border-[#1a1a2e]">
                        <span className="text-[#64748b]">Risk Level</span>
                        <Badge variant={
                          selectedProtocol.riskLevel === 'CRITICAL' ? 'danger' :
                          selectedProtocol.riskLevel === 'HIGH' ? 'warning' : 'success'
                        }>
                          {selectedProtocol.riskLevel}
                        </Badge>
                      </div>
                    </div>
                  </Card>

                  <Card variant={selectedProtocol.riskLevel === 'CRITICAL' ? 'danger' : 'default'}>
                    <div className="text-[#64748b] text-xs uppercase mb-3">Risk Indicators</div>
                    <div className="space-y-2 text-sm">
                      {[
                        { label: 'Category Risk', impact: selectedProtocol.riskScore > 50 },
                        { label: 'TVL Volatility', impact: Math.abs(selectedProtocol.change7d) > 10 },
                        { label: 'Chain Diversity', impact: selectedProtocol.chains.length < 3 },
                      ].map(indicator => (
                        <div key={indicator.label} className="flex items-center justify-between">
                          <span className="text-[#e2e8f0]">{indicator.label}</span>
                          <span className={indicator.impact ? 'text-red-400' : 'text-emerald-400'}>
                            {indicator.impact ? '⚠' : '✓'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </Card>
                </>
              ) : (
                <Card className="text-center py-12">
                  <div className="text-[#64748b] text-4xl mb-4">◎</div>
                  <p className="text-[#64748b] text-sm">
                    Select a protocol from the map to view details
                  </p>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
