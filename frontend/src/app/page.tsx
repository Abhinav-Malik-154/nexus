'use client'

import Link from 'next/link'
import { PageLayout } from '@/components/layout'
import { Card, StatCard, Button, Badge, LiveIndicator, LoadingSpinner } from '@/components/ui'
import { HighRiskPanel, RiskDistribution } from '@/components/dashboard/protocols'
import { useProtocols } from '@/hooks/useProtocols'
import { formatTVL } from '@/lib/theme'

export default function HomePage() {
  const { protocols, loading, error, stats } = useProtocols({
    limit: 200,
    minTvl: 10_000_000,
  })

  return (
    <PageLayout>
      {/* Hero Section */}
      <section className="py-16 md:py-24 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <div className="text-[#00ff9d] font-mono text-sm mb-8 flex items-center justify-center gap-2">
            <span className="text-[#64748b]">{'>'}</span>
            NEXUS v1.0 — Real-Time DeFi Anomaly Detection
            <span className="cursor-blink text-[#00ff9d]">_</span>
          </div>

          <h1 className="text-4xl md:text-6xl font-bold font-mono tracking-tight mb-6">
            <span className="text-[#e2e8f0]">DETECT.</span>
            <br />
            <span className="text-[#00ff9d]">ALERT.</span>
            <br />
            <span className="text-[#e2e8f0]">PROTECT.</span>
          </h1>

          <div className="text-[#64748b] font-mono text-sm space-y-1 mb-12">
            <p>{'/* Real-time anomaly detection for DeFi protocols */'}</p>
            <p>{'/* Monitor TVL drops, price crashes, unusual activity */'}</p>
            <p>{'/* Instant alerts when something goes wrong */'}</p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/intelligence">
              <Button variant="primary" size="lg">View Live Monitoring →</Button>
            </Link>
            <Link href="/protection">
              <Button variant="secondary" size="lg">Setup Alerts</Button>
            </Link>
          </div>

          {/* Key Difference Badge */}
          <div className="mt-8 inline-block">
            <Badge variant="warning">
              🔄 PIVOT: We detect anomalies NOW, not predict exploits LATER
            </Badge>
          </div>
        </div>
      </section>

      {/* System Status Bar */}
      <section className="border-y border-[#1a1a2e] bg-[#0f0f0f]">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <LiveIndicator />
              <span className="text-[#64748b] text-sm font-mono">Monitoring Active</span>
            </div>
            
            {loading ? (
              <LoadingSpinner size="sm" />
            ) : error ? (
              <Badge variant="danger">Error loading data</Badge>
            ) : (
              <div className="flex flex-wrap items-center gap-6 text-sm font-mono">
                <div>
                  <span className="text-[#64748b]">Protocols: </span>
                  <span className="text-[#06b6d4]">{stats.total}</span>
                </div>
                <div>
                  <span className="text-[#64748b]">TVL Monitored: </span>
                  <span className="text-[#00ff9d]">{formatTVL(stats.totalTvl)}</span>
                </div>
                <div>
                  <span className="text-[#64748b]">Anomalies: </span>
                  <span className={stats.highRiskCount > 0 ? 'text-red-400' : 'text-[#00ff9d]'}>
                    {stats.highRiskCount}
                  </span>
                </div>
                <div>
                  <span className="text-[#64748b]">Mode: </span>
                  <span className="text-[#7c3aed]">Real-Time Detection</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Main Dashboard */}
      <section className="max-w-7xl mx-auto px-4 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Protocols Monitored"
            value={loading ? '...' : stats.total}
            icon="◎"
            trend="neutral"
            trendValue="Live from DefiLlama"
          />
          <StatCard
            label="Total TVL"
            value={loading ? '...' : formatTVL(stats.totalTvl)}
            icon="◈"
            trend="neutral"
            trendValue="Across all protocols"
          />
          <StatCard
            label="Active Anomalies"
            value={loading ? '...' : stats.highRiskCount}
            icon="⚠"
            trend={stats.highRiskCount > 5 ? 'up' : 'neutral'}
            trendValue={stats.criticalCount > 0 ? `${stats.criticalCount} critical` : 'Normal levels'}
          />
          <StatCard
            label="Detection Rate"
            value={loading ? '...' : '< 1 sec'}
            icon="◉"
            trend="neutral"
            trendValue="Real-time monitoring"
          />
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          <HighRiskPanel protocols={protocols} loading={loading} title="🚨 Current Anomalies" limit={5} />
          <div className="space-y-8">
            <RiskDistribution protocols={protocols} loading={loading} />
            
            {/* Detection Method Card */}
            <Card>
              <div className="space-y-4">
                <h3 className="text-[#00ff9d] font-mono text-sm uppercase">Detection Method</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-3">
                    <span className="text-[#00ff9d] mt-0.5">✓</span>
                    <div>
                      <p className="text-[#e2e8f0] font-medium">Rule-Based Detection</p>
                      <p className="text-[#64748b] text-xs">TVL drops {'>'}20%, price crashes {'>'}30%</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-[#00ff9d] mt-0.5">✓</span>
                    <div>
                      <p className="text-[#e2e8f0] font-medium">ML Anomaly Detection</p>
                      <p className="text-[#64748b] text-xs">Isolation Forest catches subtle patterns</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="text-[#00ff9d] mt-0.5">✓</span>
                    <div>
                      <p className="text-[#e2e8f0] font-medium">Real-Time Monitoring</p>
                      <p className="text-[#64748b] text-xs">Updates every 60 seconds</p>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </section>

      {/* What We Detect */}
      <section className="border-t border-[#1a1a2e] py-16 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-[#00ff9d] font-mono text-sm uppercase tracking-wider mb-8 text-center">
            {'/* What We Detect */'}
          </h2>
          
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: '📉',
                title: 'TVL Anomalies',
                description: 'Sudden drops >20% in 1 hour or >40% in 24 hours. Often first sign of exploit.',
                example: 'Example: Euler hack - $200M TVL drained',
              },
              {
                icon: '💥',
                title: 'Price Crashes',
                description: 'Token price drops over 30% rapidly. Could indicate oracle manipulation or market panic.',
                example: 'Example: Terra/Luna collapse',
              },
              {
                icon: '🔥',
                title: 'Volume Spikes',
                description: 'Trading volume 5x+ normal. May indicate exploit draining or unusual activity.',
                example: 'Example: Wormhole bridge hack',
              },
            ].map(item => (
              <Card key={item.title} className="hover:border-[#7c3aed]/50 transition-all">
                <div className="text-4xl mb-4">{item.icon}</div>
                <h3 className="text-[#e2e8f0] font-mono font-semibold mb-2">{item.title}</h3>
                <p className="text-[#64748b] text-sm mb-3">{item.description}</p>
                <p className="text-[#475569] text-xs italic">{item.example}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Honest Disclaimer */}
      <section className="border-t border-[#1a1a2e] py-8 px-4">
        <div className="max-w-3xl mx-auto text-center text-[#475569] text-xs font-mono space-y-2">
          <p><span className="text-amber-400">⚠ What This Is:</span> Real-time anomaly detection system.</p>
          <p>
            We detect CURRENT unusual behavior (TVL drops, price crashes).
            We do NOT predict FUTURE exploits - that's too hard with limited data.
          </p>
          <p>
            Lower false alarms, more useful, actually works. Not financial advice. DYOR.
          </p>
        </div>
      </section>
    </PageLayout>
  )
}
