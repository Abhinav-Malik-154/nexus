// Design tokens and utility functions for Nexus UI

export const colors = {
  // Backgrounds
  bgPrimary: '#0a0a0a',
  bgCard: '#0f0f0f',
  bgHover: '#141420',
  
  // Borders
  border: '#1a1a2e',
  borderActive: '#7c3aed',
  
  // Text
  textPrimary: '#e2e8f0',
  textMuted: '#64748b',
  textDim: '#475569',
  
  // Brand
  accent: '#00ff9d',
  purple: '#7c3aed',
  cyan: '#06b6d4',
  orange: '#f59e0b',
  
  // Status
  success: '#00ff9d',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#06b6d4',
  
  // Risk levels
  riskLow: '#00ff9d',
  riskMedium: '#eab308',
  riskHigh: '#f59e0b',
  riskCritical: '#ef4444',
} as const

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  xxl: '48px',
} as const

export const fontSize = {
  xs: '10px',
  sm: '12px',
  md: '14px',
  lg: '16px',
  xl: '20px',
  xxl: '28px',
  hero: '48px',
} as const

export const fontWeight = {
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const

// Risk level utilities
export function getRiskColor(score: number): string {
  if (score >= 70) return colors.riskCritical
  if (score >= 55) return colors.riskHigh
  if (score >= 40) return colors.riskMedium
  return colors.riskLow
}

export function getRiskLevel(score: number): 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' {
  if (score >= 70) return 'CRITICAL'
  if (score >= 55) return 'HIGH'
  if (score >= 40) return 'MEDIUM'
  return 'LOW'
}

export function getRiskBgColor(score: number): string {
  const color = getRiskColor(score)
  return `${color}15`
}

// Format utilities
export function formatTVL(tvl: number): string {
  if (tvl >= 1e9) return `$${(tvl / 1e9).toFixed(2)}B`
  if (tvl >= 1e6) return `$${(tvl / 1e6).toFixed(1)}M`
  if (tvl >= 1e3) return `$${(tvl / 1e3).toFixed(0)}K`
  return `$${tvl.toFixed(0)}`
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`
}

export function formatAddress(address: string, chars = 4): string {
  return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`
}

export function formatTimestamp(ts: number | string): string {
  const date = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// CSS-in-JS helper
export function cn(...classes: (string | undefined | false)[]): string {
  return classes.filter(Boolean).join(' ')
}
