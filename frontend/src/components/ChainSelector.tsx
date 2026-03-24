'use client'

import { ChevronDown } from 'lucide-react'

export function ChainSelector() {
  return (
    <div
      style={{
        background: '#0f0f0f',
        border: '1px solid #1a1a2e',
        padding: '6px 12px',
        fontFamily: 'monospace',
        fontSize: '11px',
        color: '#e2e8f0',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        cursor: 'pointer',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}
    >
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: '#7c3aed',
        }}
      />
      POLYGON AMOY
      <ChevronDown size={12} style={{ color: '#64748b' }} />
    </div>
  )
}
