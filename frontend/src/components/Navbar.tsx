'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { WalletButton } from './WalletButton'
import { ChainSelector } from './ChainSelector'

const NAV_LINKS = [
  { href: '/', label: 'DASHBOARD' },
  { href: '/intelligence', label: 'INTELLIGENCE' },
  { href: '/risk-map', label: 'RISK MAP' },
  { href: '/protection', label: 'PROTECTION' },
  { href: '/alerts', label: 'ALERTS' },
]

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '48px',
        background: 'rgba(10, 10, 10, 0.9)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #1a1a2e',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        zIndex: 100,
        fontFamily: 'monospace',
      }}
    >
      {/* Left section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <Link
          href="/"
          style={{
            fontWeight: 'bold',
            fontSize: '16px',
            color: '#e2e8f0',
            textDecoration: 'none',
            letterSpacing: '0.1em',
          }}
        >
          NEXUS
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span
            className="live-indicator"
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: '#00ff9d',
            }}
          />
          <span
            style={{
              fontSize: '10px',
              color: '#00ff9d',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
            }}
          >
            LIVE
          </span>
        </div>
      </div>

      {/* Center nav links */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            style={{
              fontSize: '11px',
              textTransform: 'uppercase',
              letterSpacing: '0.15em',
              color: pathname === link.href ? '#e2e8f0' : '#64748b',
              textDecoration: 'none',
              transition: 'color 0.2s',
              borderBottom: pathname === link.href ? '1px solid #7c3aed' : 'none',
              paddingBottom: '2px',
            }}
          >
            {link.label}
          </Link>
        ))}
      </div>

      {/* Right section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <ChainSelector />
        <WalletButton />
      </div>
    </nav>
  )
}
