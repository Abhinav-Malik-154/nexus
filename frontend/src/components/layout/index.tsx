'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/theme'

const NAV_ITEMS = [
  { href: '/', label: 'Home', icon: '◈' },
  { href: '/intelligence', label: 'Intelligence', icon: '◉' },
  { href: '/risk-map', label: 'Risk Map', icon: '◎' },
  { href: '/protection', label: 'Protection', icon: '◇' },
  { href: '/alerts', label: 'Alerts', icon: '◆' },
] as const

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0a0a0a]/95 backdrop-blur-sm border-b border-[#1a1a2e]">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group">
          <span className="text-xl">◈</span>
          <span className="text-[#00ff9d] font-mono font-bold tracking-wider group-hover:text-white transition-colors">
            NEXUS
          </span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map(item => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'px-3 py-1.5 text-sm font-mono transition-all flex items-center gap-2',
                  isActive
                    ? 'text-[#00ff9d] bg-[#00ff9d]/10'
                    : 'text-[#64748b] hover:text-[#e2e8f0] hover:bg-[#1a1a2e]'
                )}
              >
                <span className="text-xs">{item.icon}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            )
          })}
        </div>

        {/* Connect Wallet (placeholder) */}
        <button className="px-4 py-1.5 bg-[#7c3aed] hover:bg-[#6d28d9] text-white text-sm font-mono transition-colors">
          Connect
        </button>
      </div>
    </nav>
  )
}

export function Footer() {
  return (
    <footer className="border-t border-[#1a1a2e] py-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-[#64748b] text-xs font-mono">
          <div className="flex items-center gap-2">
            <span>◈</span>
            <span>NEXUS Risk Oracle</span>
            <span className="text-[#1a1a2e]">|</span>
            <span>Powered by ML</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="#" className="hover:text-[#00ff9d] transition-colors">Docs</a>
            <a href="#" className="hover:text-[#00ff9d] transition-colors">GitHub</a>
            <a href="#" className="hover:text-[#00ff9d] transition-colors">Discord</a>
          </div>
        </div>
      </div>
    </footer>
  )
}

interface PageLayoutProps {
  children: React.ReactNode
  className?: string
}

export function PageLayout({ children, className }: PageLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <Navbar />
      <main className={cn('flex-1 pt-14', className)}>
        {children}
      </main>
      <Footer />
    </div>
  )
}

interface PageHeaderProps {
  title: string
  subtitle?: string
  status?: React.ReactNode
  actions?: React.ReactNode
}

export function PageHeader({ title, subtitle, status, actions }: PageHeaderProps) {
  return (
    <div className="border-b border-[#1a1a2e] bg-[#0a0a0a]">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-mono font-bold text-[#e2e8f0]">{title}</h1>
              {status}
            </div>
            {subtitle && (
              <p className="text-[#64748b] text-sm mt-1 font-mono">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      </div>
    </div>
  )
}
