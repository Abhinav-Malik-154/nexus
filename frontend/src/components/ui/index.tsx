'use client'

import { ReactNode, ButtonHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/theme'

// ═══════════════════════════════════════════════════════════════════════════
//                                CARD
// ═══════════════════════════════════════════════════════════════════════════

interface CardProps {
  children: ReactNode
  className?: string
  variant?: 'default' | 'danger' | 'success' | 'warning'
  glow?: boolean
  onClick?: () => void
}

export function Card({ children, className, variant = 'default', glow, onClick }: CardProps) {
  const borderColor = {
    default: 'border-[#1a1a2e]',
    danger: 'border-red-500/40',
    success: 'border-emerald-500/40',
    warning: 'border-amber-500/40',
  }[variant]

  const glowShadow = glow ? {
    default: '',
    danger: 'shadow-[0_0_20px_rgba(239,68,68,0.15)]',
    success: 'shadow-[0_0_20px_rgba(16,185,129,0.15)]',
    warning: 'shadow-[0_0_20px_rgba(245,158,11,0.15)]',
  }[variant] : ''

  return (
    <div 
      className={cn(
        'bg-[#0f0f0f] border rounded-none p-4',
        borderColor,
        glowShadow,
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('flex items-center justify-between mb-4', className)}>{children}</div>
}

export function CardTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h3 className={cn('text-[#00ff9d] font-mono text-sm font-semibold tracking-wide uppercase', className)}>{children}</h3>
}

export function CardContent({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('', className)}>{children}</div>
}

// ═══════════════════════════════════════════════════════════════════════════
//                               BUTTON
// ═══════════════════════════════════════════════════════════════════════════

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, className, variant = 'primary', size = 'md', loading, disabled, ...props }, ref) => {
    const variantClasses = {
      primary: 'bg-[#7c3aed] hover:bg-[#6d28d9] text-white border-[#7c3aed]',
      secondary: 'bg-transparent hover:bg-[#1a1a2e] text-[#e2e8f0] border-[#1a1a2e]',
      danger: 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/40',
      ghost: 'bg-transparent hover:bg-[#0f0f0f] text-[#64748b] border-transparent',
    }

    const sizeClasses = {
      sm: 'px-3 py-1.5 text-xs',
      md: 'px-4 py-2 text-sm',
      lg: 'px-6 py-3 text-base',
    }

    return (
      <button
        ref={ref}
        className={cn(
          'font-mono font-medium border rounded-none transition-all duration-150',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'focus:outline-none focus:ring-2 focus:ring-[#7c3aed] focus:ring-offset-2 focus:ring-offset-[#0a0a0a]',
          variantClasses[variant],
          sizeClasses[size],
          loading && 'cursor-wait',
          className
        )}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <span className="animate-pulse">⟳</span>
            <span>Loading...</span>
          </span>
        ) : children}
      </button>
    )
  }
)
Button.displayName = 'Button'

// ═══════════════════════════════════════════════════════════════════════════
//                               BADGE
// ═══════════════════════════════════════════════════════════════════════════

interface BadgeProps {
  children: ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
  pulse?: boolean
  className?: string
}

export function Badge({ children, variant = 'default', pulse, className }: BadgeProps) {
  const variantClasses = {
    default: 'bg-[#1a1a2e] text-[#e2e8f0]',
    success: 'bg-emerald-500/15 text-[#00ff9d] border border-emerald-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
    danger: 'bg-red-500/15 text-red-400 border border-red-500/30',
    info: 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30',
  }

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-mono rounded-none',
      variantClasses[variant],
      pulse && 'animate-pulse',
      className
    )}>
      {children}
    </span>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                            STAT CARD
// ═══════════════════════════════════════════════════════════════════════════

interface StatCardProps {
  label: string
  value: string | number
  subValue?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  className?: string
}

export function StatCard({ label, value, subValue, icon, trend, trendValue, className }: StatCardProps) {
  const trendColors = {
    up: 'text-emerald-400',
    down: 'text-red-400',
    neutral: 'text-[#64748b]',
  }

  const trendIcons = {
    up: '↑',
    down: '↓',
    neutral: '→',
  }

  return (
    <Card className={className}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[#64748b] text-xs font-mono uppercase tracking-wider mb-1">{label}</p>
          <p className="text-2xl font-mono font-bold text-[#e2e8f0]">{value}</p>
          {subValue && <p className="text-[#64748b] text-xs mt-1">{subValue}</p>}
          {trend && trendValue && (
            <p className={cn('text-xs mt-2 font-mono', trendColors[trend])}>
              {trendIcons[trend]} {trendValue}
            </p>
          )}
        </div>
        {icon && <div className="text-[#00ff9d] text-xl">{icon}</div>}
      </div>
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                            RISK BADGE
// ═══════════════════════════════════════════════════════════════════════════

interface RiskBadgeProps {
  score: number
  showScore?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function RiskBadge({ score, showScore = true, size = 'md' }: RiskBadgeProps) {
  const level = score >= 70 ? 'CRITICAL' : score >= 55 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW'
  const variant = level === 'CRITICAL' || level === 'HIGH' ? 'danger' : level === 'MEDIUM' ? 'warning' : 'success'
  
  const sizeClasses = {
    sm: 'text-[10px] px-1.5 py-0.5',
    md: 'text-xs px-2 py-0.5',
    lg: 'text-sm px-3 py-1',
  }

  return (
    <Badge variant={variant} pulse={level === 'CRITICAL'} className={sizeClasses[size]}>
      {showScore ? `${score.toFixed(0)}%` : level}
    </Badge>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                            LOADING
// ═══════════════════════════════════════════════════════════════════════════

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-pulse bg-[#1a1a2e] rounded', className)} />
  )
}

export function LoadingSpinner({ size = 'md', className }: { size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  }

  return (
    <div className={cn('relative', sizeClasses[size], className)}>
      <div className="absolute inset-0 border-2 border-[#1a1a2e] rounded-full" />
      <div className="absolute inset-0 border-2 border-transparent border-t-[#00ff9d] rounded-full animate-spin" />
    </div>
  )
}

export function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-4">
      <LoadingSpinner size="lg" />
      <p className="text-[#64748b] text-sm font-mono">{message}</p>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                            ERROR STATE
// ═══════════════════════════════════════════════════════════════════════════

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
}

export function ErrorState({ title = 'Error', message, onRetry }: ErrorStateProps) {
  return (
    <Card variant="danger" className="text-center py-8">
      <div className="text-red-400 text-3xl mb-4">⚠</div>
      <h3 className="text-red-400 font-mono font-semibold mb-2">{title}</h3>
      <p className="text-[#64748b] text-sm mb-4">{message}</p>
      {onRetry && (
        <Button variant="danger" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                            EMPTY STATE
// ═══════════════════════════════════════════════════════════════════════════

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ icon = '∅', title, description, action }: EmptyStateProps) {
  return (
    <Card className="text-center py-12">
      <div className="text-[#64748b] text-4xl mb-4">{icon}</div>
      <h3 className="text-[#e2e8f0] font-mono font-semibold mb-2">{title}</h3>
      <p className="text-[#64748b] text-sm mb-6 max-w-md mx-auto">{description}</p>
      {action}
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                              TABS
// ═══════════════════════════════════════════════════════════════════════════

interface TabsProps<T extends string> {
  tabs: { id: T; label: string; count?: number }[]
  activeTab: T
  onTabChange: (tab: T) => void
  className?: string
}

export function Tabs<T extends string>({ tabs, activeTab, onTabChange, className }: TabsProps<T>) {
  return (
    <div className={cn('flex gap-1 p-1 bg-[#0a0a0a] border border-[#1a1a2e]', className)}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'px-4 py-2 text-sm font-mono transition-all',
            activeTab === tab.id
              ? 'bg-[#1a1a2e] text-[#00ff9d]'
              : 'text-[#64748b] hover:text-[#e2e8f0]'
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="ml-2 text-xs opacity-60">({tab.count})</span>
          )}
        </button>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                              TOOLTIP
// ═══════════════════════════════════════════════════════════════════════════

interface TooltipProps {
  children: ReactNode
  content: string
  className?: string
}

export function Tooltip({ children, content, className }: TooltipProps) {
  return (
    <div className={cn('relative group inline-block', className)}>
      {children}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#0f0f0f] border border-[#1a1a2e] text-xs text-[#e2e8f0] font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
        {content}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//                         LIVE INDICATOR
// ═══════════════════════════════════════════════════════════════════════════

export function LiveIndicator({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span className="w-2 h-2 bg-[#00ff9d] rounded-full live-indicator" />
      <span className="text-[#00ff9d] text-xs font-mono">LIVE</span>
    </span>
  )
}
