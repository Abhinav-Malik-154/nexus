'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useLiveRiskIntelligence, getRiskLevel, getRiskColor, formatTVL, formatTimestamp } from '../../hooks/useLiveRiskIntelligence'
import { useLiveSecurityFeed } from '../../hooks/useLiveSecurityFeed'

// Types for our enhanced risk data
interface RiskIntelligence {
  protocol: string
  slug: string
  riskScore: number
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  tvl: number
  category: string
  indicators: string[]
  prediction: string
  confidence: number
}

interface SecurityUpdate {
  id: string
  title: string
  type: 'EXPLOIT' | 'PATCH' | 'VULNERABILITY' | 'ALERT'
  description: string
  impact: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  date: string
  affected: string[]
  url?: string
}

interface AttackVector {
  name: string
  description: string
  frequency: string
  prevention: string[]
  examples: string[]
}

const SECURITY_UPDATES: SecurityUpdate[] = [] // Replaced with live security feed

const ATTACK_VECTORS: AttackVector[] = [
  {
    name: 'Flash Loan Attacks',
    description: 'Large uncollateralized loans used to manipulate markets within single transaction',
    frequency: 'Monthly',
    prevention: ['Oracle diversification', 'Transaction delays', 'Collateral requirements'],
    examples: ['bZx (2020)', 'Harvest Finance (2020)', 'Alpha Finance (2021)']
  },
  {
    name: 'Oracle Manipulation',
    description: 'Attackers manipulate price feeds to create arbitrage opportunities',
    frequency: 'Weekly',
    prevention: ['Multiple oracle sources', 'Time-weighted prices', 'Circuit breakers'],
    examples: ['Inverse Finance (2022)', 'Mango Markets (2022)']
  },
  {
    name: 'Bridge Exploits',
    description: 'Cross-chain bridge vulnerabilities allowing double-spending or fund drainage',
    frequency: 'Quarterly',
    prevention: ['Multi-sig validation', 'Withdrawal delays', 'Regular audits'],
    examples: ['Ronin Bridge ($625M)', 'Wormhole ($325M)', 'Nomad Bridge ($190M)']
  },
  {
    name: 'Governance Attacks',
    description: 'Malicious proposals or token voting manipulation',
    frequency: 'Rare',
    prevention: ['Vote delegation limits', 'Proposal delays', 'Veto mechanisms'],
    examples: ['BeanStalk (2022)', 'Tornado Cash governance']
  }
]

export default function IntelligencePage() {
  const [activeTab, setActiveTab] = useState<'risks' | 'attacks' | 'news'>('risks')
  const {
    data: liveData,
    loading,
    error,
    lastFetch,
    refetch,
    highRiskProtocols,
    criticalRiskProtocols,
    modelStats
  } = useLiveRiskIntelligence({
    limit: 20,
    minRisk: 0,
    refreshInterval: 60000,
    autoRefresh: true
  })

  // Live security feed
  const {
    data: securityData,
    loading: securityLoading,
    error: securityError,
    refresh: refreshSecurity,
    lastUpdated: securityLastUpdated
  } = useLiveSecurityFeed(300000) // 5 minutes refresh

  // Transform live security threats to SecurityUpdate format
  const liveSecurityUpdates: SecurityUpdate[] = (securityData?.threats || []).map(threat => ({
    id: threat.id,
    title: threat.title,
    type: determineUpdateType(threat.type),
    description: threat.title, // API returns title, could expand with more details
    impact: mapSeverityToImpact(threat.severity),
    date: new Date(threat.date).toISOString().split('T')[0],
    affected: threat.protocols || threat.affected || [],
    url: threat.source === 'rekt.news' ? `https://rekt.news/` :
          threat.source === 'defisafety.com' ? `https://defisafety.com/` :
          undefined
  }))

  function determineUpdateType(threatType: string): 'EXPLOIT' | 'PATCH' | 'VULNERABILITY' | 'ALERT' {
    if (threatType.includes('Flash Loan') || threatType.includes('Bridge Exploit')) return 'EXPLOIT'
    if (threatType.includes('MEV') || threatType.includes('Oracle')) return 'VULNERABILITY'
    if (threatType.includes('Security Incident')) return 'ALERT'
    return 'ALERT'
  }

  function mapSeverityToImpact(severity: string): 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' {
    switch (severity) {
      case 'CRITICAL': return 'CRITICAL'
      case 'HIGH': return 'HIGH'
      case 'MEDIUM': return 'MEDIUM'
      case 'LOW': return 'LOW'
      default: return 'MEDIUM'
    }
  }

  const [isLive, setIsLive] = useState(true)

  // Simulate live indicator pulsing
  useEffect(() => {
    const interval = setInterval(() => {
      setIsLive(prev => !prev)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Transform live data to enhanced format
  const enhancedRisks: RiskIntelligence[] = (liveData?.risks || []).map(risk => ({
    protocol: risk.protocol,
    slug: risk.slug,
    riskScore: risk.riskScore,
    level: risk.level,
    tvl: risk.tvl,
    category: risk.category,
    indicators: generateRiskIndicators(risk),
    prediction: generatePrediction(risk),
    confidence: risk.confidence
  }))

  function generateRiskIndicators(risk: any): string[] {
    const indicators = []

    if (risk.change1d < -10) indicators.push('TVL Drop Alert')
    if (risk.change7d < -20) indicators.push('Weekly Decline')
    if (risk.riskScore > 70) indicators.push('High Risk Model Output')
    if (risk.category === 'Bridge') indicators.push('Bridge Vulnerability')
    if (risk.category === 'Lending') indicators.push('Liquidation Risk')
    if (risk.category === 'Liquid Staking') indicators.push('Validator Risk')
    if (risk.tvl > 10e9) indicators.push('High Value Target')
    if (risk.confidence < 0.7) indicators.push('Uncertain Prediction')

    return indicators.length > 0 ? indicators : ['Normal Operations']
  }

  function generatePrediction(risk: any): string {
    if (risk.level === 'CRITICAL') return 'High probability exploit risk detected'
    if (risk.level === 'HIGH') return 'Elevated risk indicators present'
    if (risk.level === 'MEDIUM') return 'Monitoring for developing threats'
    return 'Low risk, stable operations expected'
  }

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'CRITICAL': return '#ef4444'
      case 'HIGH': return '#f59e0b'
      case 'MEDIUM': return '#eab308'
      case 'LOW': return '#00ff9d'
      default: return '#64748b'
    }
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', background: '#0a0a0a', padding: '80px 24px' }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ color: '#00ff9d', fontFamily: 'monospace', fontSize: '14px', marginBottom: '8px' }}>
            {'>'} NEXUS INTELLIGENCE HQ
          </div>
          <h1 style={{ fontFamily: 'monospace', fontSize: '36px', color: '#e2e8f0', margin: 0 }}>
            Live Risk Intelligence & Attack Prevention
          </h1>
          <p style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '13px', marginTop: '8px' }}>
            // AI-powered threat analysis • Real-time predictions • Attack vector intelligence
          </p>
        </div>

        {/* Model Performance Banner */}
        <div style={{
          background: (modelStats?.isActive && !loading) ? 'linear-gradient(90deg, #00ff9d15 0%, #00ff9d30 50%, #00ff9d15 100%)' : '#0f0f0f',
          border: (modelStats?.isActive && !loading) ? '1px solid #00ff9d30' : '1px solid #1a1a2e',
          padding: '20px',
          marginBottom: '24px',
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: loading ? '#f59e0b' : (modelStats?.isActive ? '#00ff9d' : '#64748b'),
                  animation: loading ? 'pulse 2s infinite' : (modelStats?.isActive ? 'pulse 2s infinite' : 'none')
                }} />
                <span style={{ color: loading ? '#f59e0b' : '#00ff9d', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.15em', fontFamily: 'monospace' }}>
                  GNN MODEL v3 {loading ? 'UPDATING' : (modelStats?.isActive ? 'LIVE' : 'OFFLINE')}
                </span>
              </div>
              {loading ? (
                <div style={{ color: '#f59e0b', fontSize: '14px', fontFamily: 'monospace' }}>
                  Loading live risk data...
                </div>
              ) : error ? (
                <div style={{ color: '#ef4444', fontSize: '14px', fontFamily: 'monospace' }}>
                  Error: {error} (using fallback data)
                </div>
              ) : (
                <div style={{ color: '#e2e8f0', fontSize: '14px', fontFamily: 'monospace' }}>
                  Precision: {modelStats?.precision?.toFixed(1) || 0}% • F1: {modelStats?.f1?.toFixed(1) || 0}% • AUC: {modelStats?.auc?.toFixed(1) || 0}% • Monitoring: {modelStats?.protocolsMonitored || 0}+ protocols
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ color: '#64748b', fontSize: '10px', fontFamily: 'monospace' }}>
                LAST UPDATE: {lastFetch ? formatTimestamp(lastFetch.toISOString()).toUpperCase() : 'INITIALIZING'}
              </div>
              <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                <button
                  onClick={refetch}
                  style={{
                    background: 'transparent',
                    border: '1px solid #00ff9d30',
                    color: '#00ff9d',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    textDecoration: 'none',
                    cursor: 'pointer',
                    padding: '4px 8px'
                  }}
                >
                  REFRESH
                </button>
                <Link href="/risk-map" style={{ color: '#00ff9d', fontSize: '11px', fontFamily: 'monospace', textDecoration: 'none' }}>
                  VIEW RISK MAP →
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '2px', marginBottom: '24px' }}>
          {[
            { key: 'risks', label: 'LIVE RISKS', icon: '⚠️', status: loading ? 'UPDATING' : (error ? 'ERROR' : 'LIVE') },
            { key: 'attacks', label: 'ATTACK INTEL', icon: '🛡️', status: 'STATIC' },
            { key: 'news', label: 'LIVE SECURITY FEED', icon: '📡', status: securityLoading ? 'UPDATING' : (securityError ? 'ERROR' : 'LIVE') },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              style={{
                background: activeTab === tab.key ? '#f59e0b' : '#0f0f0f',
                color: activeTab === tab.key ? '#0a0a0a' : '#64748b',
                border: activeTab === tab.key ? '1px solid #f59e0b' : '1px solid #1a1a2e',
                padding: '12px 24px',
                fontFamily: 'monospace',
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                cursor: 'pointer',
                fontWeight: 'bold',
                transition: 'all 0.2s ease',
                position: 'relative'
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
                <span>{tab.icon} {tab.label}</span>
                <span style={{
                  fontSize: '8px',
                  color: tab.status === 'LIVE' ? '#00ff9d' : tab.status === 'UPDATING' ? '#f59e0b' : tab.status === 'ERROR' ? '#ef4444' : '#64748b'
                }}>
                  {tab.status}
                </span>
              </div>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'risks' && (
          <div>
            {loading && (
              <div style={{
                textAlign: 'center',
                padding: '40px',
                color: '#64748b',
                fontFamily: 'monospace'
              }}>
                <div style={{ marginBottom: '16px' }}>🔄 Fetching live risk data...</div>
                <div style={{ fontSize: '12px' }}>Connecting to GNN model...</div>
              </div>
            )}

            {error && !loading && (
              <div style={{
                textAlign: 'center',
                padding: '40px',
                border: '1px solid #ef444430',
                background: '#ef444410',
                color: '#ef4444',
                fontFamily: 'monospace',
                marginBottom: '24px'
              }}>
                <div style={{ marginBottom: '8px' }}>⚠️ Connection Error</div>
                <div style={{ fontSize: '12px' }}>{error}</div>
                <button
                  onClick={refetch}
                  style={{
                    marginTop: '12px',
                    background: '#ef4444',
                    color: '#fff',
                    border: 'none',
                    padding: '8px 16px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    cursor: 'pointer'
                  }}
                >
                  RETRY CONNECTION
                </button>
              </div>
            )}

            {enhancedRisks.length > 0 && (
              <>
                <div style={{
                  marginBottom: '16px',
                  padding: '12px 16px',
                  background: '#0f0f0f',
                  border: '1px solid #1a1a2e',
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontFamily: 'monospace',
                  fontSize: '11px'
                }}>
                  <span style={{ color: '#00ff9d' }}>
                    📊 ACTIVE MONITORING: {enhancedRisks.length} protocols
                  </span>
                  <span style={{ color: '#ef4444' }}>
                    🚨 HIGH RISK: {criticalRiskProtocols.length + highRiskProtocols.filter(p => p.riskScore < 80).length}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '16px' }}>
                  {enhancedRisks.map(risk => (
                    <div key={risk.protocol} style={{
                      background: '#0f0f0f',
                      border: `1px solid ${getRiskColor(risk.level)}30`,
                      padding: '20px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                        <div>
                          <div style={{ color: '#e2e8f0', fontSize: '16px', fontWeight: 'bold', fontFamily: 'monospace' }}>
                            {risk.protocol}
                          </div>
                          <div style={{ color: '#64748b', fontSize: '12px', fontFamily: 'monospace' }}>
                            {risk.category}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{
                            color: getRiskColor(risk.level),
                            fontSize: '24px',
                            fontWeight: 'bold',
                            fontFamily: 'monospace'
                          }}>
                            {risk.riskScore.toFixed(1)}%
                          </div>
                          <div style={{
                            background: `${getRiskColor(risk.level)}15`,
                            border: `1px solid ${getRiskColor(risk.level)}30`,
                            color: getRiskColor(risk.level),
                            padding: '2px 8px',
                            fontSize: '9px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.1em',
                            fontFamily: 'monospace'
                          }}>
                            {risk.level}
                          </div>
                        </div>
                      </div>

                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '8px', fontFamily: 'monospace' }}>
                          AI PREDICTION ({Math.round(risk.confidence * 100)}% CONFIDENCE)
                        </div>
                        <div style={{ color: '#e2e8f0', fontSize: '13px', fontFamily: 'monospace' }}>
                          {risk.prediction}
                        </div>
                      </div>

                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '8px', fontFamily: 'monospace' }}>
                          RISK INDICATORS
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {risk.indicators.map(indicator => (
                            <span key={indicator} style={{
                              background: '#1a1a2e',
                              color: '#e2e8f0',
                              padding: '2px 6px',
                              fontSize: '10px',
                              fontFamily: 'monospace',
                              border: '1px solid #374151'
                            }}>
                              {indicator}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '16px', borderTop: '1px solid #1a1a2e' }}>
                        <div style={{ color: '#64748b', fontSize: '11px', fontFamily: 'monospace' }}>
                          TVL: {formatTVL(risk.tvl)}
                        </div>
                        <Link href={`/protection?protocol=${risk.slug}`} style={{
                          color: '#00ff9d',
                          fontSize: '10px',
                          fontFamily: 'monospace',
                          textDecoration: 'none',
                          textTransform: 'uppercase',
                          letterSpacing: '0.1em'
                        }}>
                          PROTECT FUNDS →
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {!loading && !error && enhancedRisks.length === 0 && (
              <div style={{
                textAlign: 'center',
                padding: '60px',
                color: '#64748b',
                fontFamily: 'monospace'
              }}>
                <div style={{ marginBottom: '16px', fontSize: '48px' }}>🔍</div>
                <div style={{ marginBottom: '8px' }}>No risk data available</div>
                <div style={{ fontSize: '12px' }}>Model may be initializing or no protocols meet current filter criteria</div>
                <button
                  onClick={refetch}
                  style={{
                    marginTop: '16px',
                    background: '#00ff9d',
                    color: '#0a0a0a',
                    border: 'none',
                    padding: '8px 16px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    cursor: 'pointer'
                  }}
                >
                  RETRY FETCH
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'attacks' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '16px' }}>
            {ATTACK_VECTORS.map(attack => (
              <div key={attack.name} style={{
                background: '#0f0f0f',
                border: '1px solid #1a1a2e',
                padding: '24px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                  <div>
                    <div style={{ color: '#f59e0b', fontSize: '16px', fontWeight: 'bold', fontFamily: 'monospace' }}>
                      {attack.name}
                    </div>
                    <div style={{ color: '#64748b', fontSize: '11px', fontFamily: 'monospace' }}>
                      FREQUENCY: {attack.frequency.toUpperCase()}
                    </div>
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: '1.5', fontFamily: 'monospace' }}>
                    {attack.description}
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#00ff9d', fontSize: '11px', marginBottom: '8px', fontFamily: 'monospace' }}>
                    PREVENTION STRATEGIES
                  </div>
                  {attack.prevention.map(strategy => (
                    <div key={strategy} style={{
                      color: '#e2e8f0',
                      fontSize: '12px',
                      marginBottom: '4px',
                      fontFamily: 'monospace',
                      paddingLeft: '8px',
                      borderLeft: '2px solid #00ff9d'
                    }}>
                      {strategy}
                    </div>
                  ))}
                </div>

                <div>
                  <div style={{ color: '#ef4444', fontSize: '11px', marginBottom: '8px', fontFamily: 'monospace' }}>
                    HISTORICAL ATTACKS
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {attack.examples.map(example => (
                      <span key={example} style={{
                        background: '#ef444415',
                        border: '1px solid #ef444430',
                        color: '#ef4444',
                        padding: '2px 6px',
                        fontSize: '10px',
                        fontFamily: 'monospace'
                      }}>
                        {example}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'news' && (
          <div>
            {/* Security Feed Status */}
            <div style={{
              marginBottom: '24px',
              padding: '16px',
              background: securityLoading ? '#f59e0b15' : (securityError ? '#ef444415' : '#00ff9d15'),
              border: `1px solid ${securityLoading ? '#f59e0b30' : (securityError ? '#ef444430' : '#00ff9d30')}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: securityLoading ? '#f59e0b' : (securityError ? '#ef4444' : '#00ff9d'),
                  animation: securityLoading ? 'pulse 2s infinite' : 'pulse 2s infinite'
                }} />
                <span style={{
                  color: securityLoading ? '#f59e0b' : (securityError ? '#ef4444' : '#00ff9d'),
                  fontSize: '11px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.15em',
                  fontFamily: 'monospace'
                }}>
                  LIVE SECURITY FEED {securityLoading ? 'UPDATING' : (securityError ? 'ERROR' : 'ACTIVE')}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ color: '#64748b', fontSize: '10px', fontFamily: 'monospace' }}>
                  {securityLastUpdated ?
                    `UPDATED: ${securityLastUpdated.toLocaleTimeString()} • ${securityData?.summary.total || 0} THREATS` :
                    'INITIALIZING...'}
                </span>
                <button
                  onClick={refreshSecurity}
                  style={{
                    background: 'transparent',
                    border: '1px solid #00ff9d30',
                    color: '#00ff9d',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    padding: '4px 8px',
                    cursor: 'pointer'
                  }}
                >
                  REFRESH
                </button>
              </div>
            </div>

            {securityError && (
              <div style={{
                background: '#ef444415',
                border: '1px solid #ef444430',
                padding: '20px',
                marginBottom: '24px',
                textAlign: 'center'
              }}>
                <div style={{ color: '#ef4444', fontSize: '14px', fontFamily: 'monospace', marginBottom: '8px' }}>
                  ⚠️ Live Security Feed Error
                </div>
                <div style={{ color: '#64748b', fontSize: '12px', fontFamily: 'monospace', marginBottom: '12px' }}>
                  {securityError}
                </div>
                <div style={{ color: '#e2e8f0', fontSize: '11px', fontFamily: 'monospace' }}>
                  Showing fallback threat data while service reconnects
                </div>
              </div>
            )}

            {securityLoading && liveSecurityUpdates.length === 0 && (
              <div style={{
                textAlign: 'center',
                padding: '40px',
                color: '#64748b',
                fontFamily: 'monospace'
              }}>
                <div style={{ marginBottom: '16px' }}>🔄 Loading live security intelligence...</div>
                <div style={{ fontSize: '12px' }}>Fetching threats from multiple sources...</div>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {liveSecurityUpdates.length > 0 ? (
                liveSecurityUpdates.map(update => (
                  <div key={update.id} style={{
                    background: '#0f0f0f',
                    border: '1px solid #1a1a2e',
                    padding: '20px',
                    display: 'flex',
                    gap: '20px'
                  }}>
                    <div style={{
                      background: `${getImpactColor(update.impact)}15`,
                      border: `1px solid ${getImpactColor(update.impact)}30`,
                      color: getImpactColor(update.impact),
                      padding: '4px 8px',
                      fontSize: '9px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      fontFamily: 'monospace',
                      height: 'fit-content'
                    }}>
                      {update.type}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                        <div style={{ color: '#e2e8f0', fontSize: '16px', fontWeight: 'bold', fontFamily: 'monospace' }}>
                          {update.title}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                          <div style={{ color: '#64748b', fontSize: '11px', fontFamily: 'monospace' }}>
                            {new Date(update.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                          </div>
                          <div style={{ color: '#64748b', fontSize: '10px', fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <div style={{
                              width: '6px',
                              height: '6px',
                              borderRadius: '50%',
                              background: '#00ff9d',
                              animation: 'pulse 2s infinite'
                            }} />
                            LIVE
                          </div>
                        </div>
                      </div>

                      <div style={{ color: '#e2e8f0', fontSize: '13px', marginBottom: '12px', lineHeight: '1.5', fontFamily: 'monospace' }}>
                        {update.description}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                          <div style={{ color: '#64748b', fontSize: '11px', fontFamily: 'monospace' }}>
                            {update.affected.length > 0 ? 'AFFECTED:' : 'MONITORING:'}
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {(update.affected.length > 0 ? update.affected : ['DeFi Ecosystem']).slice(0, 3).map(protocol => (
                              <span key={protocol} style={{
                                background: '#374151',
                                color: '#e2e8f0',
                                padding: '2px 6px',
                                fontSize: '10px',
                                fontFamily: 'monospace'
                              }}>
                                {protocol}
                              </span>
                            ))}
                            {update.affected.length > 3 && (
                              <span style={{
                                color: '#64748b',
                                fontSize: '10px',
                                fontFamily: 'monospace'
                              }}>
                                +{update.affected.length - 3} more
                              </span>
                            )}
                          </div>
                        </div>

                        {update.url && (
                          <a
                            href={update.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              color: '#00ff9d',
                              fontSize: '10px',
                              fontFamily: 'monospace',
                              textDecoration: 'none',
                              textTransform: 'uppercase',
                              letterSpacing: '0.1em',
                              border: '1px solid #00ff9d30',
                              padding: '4px 8px',
                              transition: 'all 0.2s ease'
                            }}
                            onMouseOver={(e) => {
                              e.currentTarget.style.background = '#00ff9d15';
                              e.currentTarget.style.borderColor = '#00ff9d';
                            }}
                            onMouseOut={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.borderColor = '#00ff9d30';
                            }}
                          >
                            VIEW SOURCE →
                          </a>
                        )}
                      </div>
                    </div>

                    <div style={{
                      background: `${getImpactColor(update.impact)}15`,
                      border: `1px solid ${getImpactColor(update.impact)}30`,
                      color: getImpactColor(update.impact),
                      padding: '2px 8px',
                      fontSize: '9px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      fontFamily: 'monospace',
                      height: 'fit-content'
                    }}>
                      {update.impact}
                    </div>
                  </div>
                ))
              ) : !securityLoading && !securityError && (
                <div style={{
                  textAlign: 'center',
                  padding: '60px',
                  color: '#64748b',
                  fontFamily: 'monospace',
                  background: '#0f0f0f',
                  border: '1px solid #1a1a2e'
                }}>
                  <div style={{ marginBottom: '16px', fontSize: '48px' }}>📡</div>
                  <div style={{ marginBottom: '8px' }}>No security threats detected</div>
                  <div style={{ fontSize: '12px', marginBottom: '16px' }}>All monitored systems appear secure</div>
                  <button
                    onClick={refreshSecurity}
                    style={{
                      background: '#00ff9d',
                      color: '#0a0a0a',
                      border: 'none',
                      padding: '8px 16px',
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      cursor: 'pointer'
                    }}
                  >
                    REFRESH FEED
                  </button>
                </div>
              )}

              {liveSecurityUpdates.length > 0 && (
                <div style={{
                  background: '#0f0f0f',
                  border: '1px solid #00ff9d30',
                  padding: '20px',
                  textAlign: 'center'
                }}>
                  <div style={{ color: '#00ff9d', fontSize: '12px', fontFamily: 'monospace', marginBottom: '8px' }}>
                    STAY PROTECTED
                  </div>
                  <div style={{ color: '#e2e8f0', fontSize: '13px', fontFamily: 'monospace', marginBottom: '16px' }}>
                    Enable automated protection to react instantly to emerging threats
                  </div>
                  <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                    <Link href="/protection" style={{
                      background: '#00ff9d',
                      color: '#0a0a0a',
                      padding: '8px 16px',
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      textDecoration: 'none',
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      fontWeight: 'bold'
                    }}>
                      SETUP PROTECTION
                    </Link>
                    <button
                      onClick={refreshSecurity}
                      style={{
                        background: 'transparent',
                        border: '1px solid #00ff9d',
                        color: '#00ff9d',
                        padding: '8px 16px',
                        fontSize: '11px',
                        fontFamily: 'monospace',
                        cursor: 'pointer',
                        textTransform: 'uppercase',
                        letterSpacing: '0.1em'
                      }}
                    >
                      UPDATE FEED
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}