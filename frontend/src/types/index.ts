// Types for the Nexus DeFi Risk Platform

// ═══════════════════════════════════════════════════════════════════════════
//                              RISK TYPES
// ═══════════════════════════════════════════════════════════════════════════

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface RiskScore {
  protocolId: `0x${string}`
  score: number
  timestamp: number
  level: RiskLevel
}

export interface Protocol {
  id: string
  slug: string
  name: string
  category: string
  tvl: number
  chains: string[]
  riskScore: number
  riskLevel: RiskLevel
  change1d: number
  change7d: number
}

export interface ProtocolRisk extends Protocol {
  indicators: RiskIndicator[]
  prediction: string
  confidence: number
  lastUpdated: string
}

export interface RiskIndicator {
  name: string
  value: number
  impact: 'positive' | 'negative' | 'neutral'
  description: string
}

// ═══════════════════════════════════════════════════════════════════════════
//                           PROTECTION TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface ProtectionRule {
  id: number
  protocolId: `0x${string}`
  protocolName: string
  riskThreshold: number
  token: `0x${string}`
  safeAddress: `0x${string}`
  active: boolean
  triggered: boolean
  createdAt: number
}

export interface VaultBalance {
  token: `0x${string}`
  symbol: string
  balance: bigint
  decimals: number
}

export interface ProtectionEvent {
  type: 'triggered' | 'deposit' | 'withdraw' | 'rule_added' | 'rule_removed'
  timestamp: number
  txHash: `0x${string}`
  details: Record<string, unknown>
}

// ═══════════════════════════════════════════════════════════════════════════
//                           SECURITY TYPES
// ═══════════════════════════════════════════════════════════════════════════

export type SecurityEventType = 'EXPLOIT' | 'VULNERABILITY' | 'PATCH' | 'ALERT'

export interface SecurityEvent {
  id: string
  type: SecurityEventType
  title: string
  description: string
  severity: RiskLevel
  affectedProtocols: string[]
  date: string
  source: string
  url?: string
}

export interface AttackVector {
  name: string
  description: string
  frequency: string
  prevention: string[]
  examples: string[]
}

// ═══════════════════════════════════════════════════════════════════════════
//                           MODEL TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface ModelMetrics {
  precision: number
  recall: number
  f1: number
  aucRoc: number
  version: string
  lastUpdated: string
}

export interface SystemStatus {
  protocolCount: number
  highRiskCount: number
  criticalCount: number
  modelVersion: string
  modelMetrics: ModelMetrics
  lastUpdate: string
  isLive: boolean
}

// ═══════════════════════════════════════════════════════════════════════════
//                           API TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface ApiResponse<T> {
  data: T
  timestamp: string
  status: 'success' | 'error'
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

// ═══════════════════════════════════════════════════════════════════════════
//                           TOKEN TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface Token {
  address: `0x${string}`
  symbol: string
  name: string
  decimals: number
  logoUrl?: string
}

export const SUPPORTED_TOKENS: Token[] = [
  { address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', symbol: 'USDC', name: 'USD Coin', decimals: 6 },
  { address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', symbol: 'USDT', name: 'Tether', decimals: 6 },
  { address: '0x6B175474E89094C44Da98b954EescdeCB5cE5cBd4', symbol: 'DAI', name: 'Dai', decimals: 18 },
]
