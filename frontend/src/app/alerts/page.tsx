'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAccount } from 'wagmi'
import {
  useHighRiskAlerts,
  useProtectionTriggeredEvents,
  useHighRiskProtocols,
  useRiskScoreById,
  useProtocolName,
  getRiskColor,
  getRiskLevel,
  type HighRiskAlertEvent,
  type ProtectionTriggeredEvent,
} from '@/hooks/useNexus'
import { formatUnits } from 'viem'

interface Alert {
  id: string
  type: 'risk' | 'protection'
  timestamp: number
  data: HighRiskAlertEvent | ProtectionTriggeredEvent
}

// Mock historical alerts (in production, fetch from indexer)
const MOCK_ALERTS: Alert[] = [
  {
    id: '1',
    type: 'risk',
    timestamp: Date.now() - 1000 * 60 * 15,
    data: {
      protocolId: '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef' as `0x${string}`,
      riskScore: 72n,
      timestamp: BigInt(Math.floor((Date.now() - 1000 * 60 * 15) / 1000)),
    },
  },
  {
    id: '2',
    type: 'risk',
    timestamp: Date.now() - 1000 * 60 * 45,
    data: {
      protocolId: '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890' as `0x${string}`,
      riskScore: 85n,
      timestamp: BigInt(Math.floor((Date.now() - 1000 * 60 * 45) / 1000)),
    },
  },
]

function AlertCard({ alert }: { alert: Alert }) {
  const isRisk = alert.type === 'risk'
  const data = alert.data as HighRiskAlertEvent
  const protData = alert.data as ProtectionTriggeredEvent
  const { data: name } = useProtocolName(data.protocolId)

  const timeAgo = (ts: number) => {
    const diff = Date.now() - ts
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  return (
    <div
      style={{
        background: '#0f0f0f',
        border: `1px solid ${isRisk ? '#f59e0b30' : '#7c3aed30'}`,
        borderLeft: `3px solid ${isRisk ? '#f59e0b' : '#7c3aed'}`,
        padding: '16px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            color: isRisk ? '#f59e0b' : '#7c3aed',
            background: isRisk ? '#f59e0b15' : '#7c3aed15',
            border: `1px solid ${isRisk ? '#f59e0b30' : '#7c3aed30'}`,
            padding: '2px 8px',
            fontSize: '9px',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontFamily: 'monospace',
          }}>
            {isRisk ? 'HIGH RISK' : 'PROTECTION'}
          </span>
          {isRisk && (
            <span style={{
              color: getRiskColor(Number(data.riskScore)),
              background: `${getRiskColor(Number(data.riskScore))}15`,
              border: `1px solid ${getRiskColor(Number(data.riskScore))}30`,
              padding: '2px 8px',
              fontSize: '9px',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              fontFamily: 'monospace',
            }}>
              {getRiskLevel(Number(data.riskScore))}
            </span>
          )}
        </div>
        <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '11px' }}>
          {timeAgo(alert.timestamp)}
        </span>
      </div>

      <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px', fontWeight: 'bold', marginBottom: '8px' }}>
        {name || data.protocolId.slice(0, 10) + '...'}
      </div>

      {isRisk ? (
        <div style={{ display: 'flex', gap: '24px' }}>
          <div>
            <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '2px' }}>
              Risk Score
            </div>
            <div style={{ color: getRiskColor(Number(data.riskScore)), fontFamily: 'monospace', fontSize: '20px', fontWeight: 'bold' }}>
              {Number(data.riskScore)}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <div>
            <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '2px' }}>
              Amount
            </div>
            <div style={{ color: '#00ff9d', fontFamily: 'monospace', fontSize: '14px' }}>
              {formatUnits(protData.amount, 6)} USDC
            </div>
          </div>
          <div>
            <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '2px' }}>
              Risk Score
            </div>
            <div style={{ color: getRiskColor(Number(protData.riskScore)), fontFamily: 'monospace', fontSize: '14px' }}>
              {Number(protData.riskScore)}
            </div>
          </div>
          <div>
            <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '2px' }}>
              Safe Address
            </div>
            <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px' }}>
              {protData.safeAddress?.slice(0, 8)}...
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function AlertsPage() {
  const { address } = useAccount()
  const [alerts, setAlerts] = useState<Alert[]>(MOCK_ALERTS)
  const [filter, setFilter] = useState<'all' | 'risk' | 'protection'>('all')

  const { data: highRiskProtocols } = useHighRiskProtocols()

  // Listen for new high risk alerts
  const handleRiskAlert = useCallback((event: HighRiskAlertEvent) => {
    const newAlert: Alert = {
      id: `risk-${Date.now()}`,
      type: 'risk',
      timestamp: Date.now(),
      data: event,
    }
    setAlerts(prev => [newAlert, ...prev])
  }, [])

  // Listen for protection triggers
  const handleProtection = useCallback((event: ProtectionTriggeredEvent) => {
    const newAlert: Alert = {
      id: `prot-${Date.now()}`,
      type: 'protection',
      timestamp: Date.now(),
      data: event,
    }
    setAlerts(prev => [newAlert, ...prev])
  }, [])

  useHighRiskAlerts(handleRiskAlert)
  useProtectionTriggeredEvents(address, handleProtection)

  const filteredAlerts = filter === 'all' ? alerts : alerts.filter(a => a.type === filter)

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', background: '#0a0a0a', padding: '80px 24px' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ color: '#00ff9d', fontFamily: 'monospace', fontSize: '14px', marginBottom: '8px' }}>
            {'>'} ALERTS
          </div>
          <h1 style={{ fontFamily: 'monospace', fontSize: '36px', color: '#e2e8f0', margin: 0 }}>
            Risk Alerts
          </h1>
          <p style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '13px', marginTop: '8px' }}>
            // Real-time notifications for high-risk events and protection triggers
          </p>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
          {[
            { label: 'High Risk Now', value: highRiskProtocols?.length?.toString() ?? '0', color: '#ef4444' },
            { label: 'Today\'s Alerts', value: alerts.filter(a => a.timestamp > Date.now() - 86400000).length.toString(), color: '#f59e0b' },
            { label: 'Protections Triggered', value: alerts.filter(a => a.type === 'protection').length.toString(), color: '#7c3aed' },
          ].map(s => (
            <div key={s.label} style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px' }}>
              <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '4px' }}>
                {s.label}
              </div>
              <div style={{ color: s.color, fontFamily: 'monospace', fontSize: '28px', fontWeight: 'bold' }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>

        {/* Filter */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
          {(['all', 'risk', 'protection'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                background: filter === f ? '#1a1a2e' : 'transparent',
                border: `1px solid ${filter === f ? '#7c3aed' : '#1a1a2e'}`,
                color: filter === f ? '#e2e8f0' : '#64748b',
                padding: '8px 16px',
                fontFamily: 'monospace',
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                cursor: 'pointer',
              }}
            >
              {f === 'all' ? 'ALL' : f === 'risk' ? 'HIGH RISK' : 'PROTECTION'}
            </button>
          ))}
        </div>

        {/* Alerts List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredAlerts.length === 0 ? (
            <div style={{
              background: '#0f0f0f',
              border: '1px solid #1a1a2e',
              padding: '60px 24px',
              textAlign: 'center',
            }}>
              <div style={{ color: '#00ff9d', fontSize: '32px', marginBottom: '12px' }}>✓</div>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px', marginBottom: '8px' }}>
                All Clear
              </div>
              <div style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '12px' }}>
                No alerts to display
              </div>
            </div>
          ) : (
            filteredAlerts.map(alert => <AlertCard key={alert.id} alert={alert} />)
          )}
        </div>

        {/* Legend */}
        <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '16px', marginTop: '24px' }}>
          <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '12px' }}>
            ALERT TYPES
          </div>
          <div style={{ display: 'flex', gap: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '3px', height: '16px', background: '#f59e0b' }} />
              <div>
                <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px', fontWeight: 'bold' }}>HIGH RISK</div>
                <div style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '10px' }}>Protocol risk score exceeded threshold</div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '3px', height: '16px', background: '#7c3aed' }} />
              <div>
                <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px', fontWeight: 'bold' }}>PROTECTION</div>
                <div style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '10px' }}>Funds auto-transferred to safe address</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
