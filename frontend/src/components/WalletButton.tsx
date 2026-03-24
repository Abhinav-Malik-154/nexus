'use client'

import { useAccount, useConnect, useDisconnect } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { Wallet, LogOut } from 'lucide-react'

export function WalletButton() {
  const { address, isConnected } = useAccount()
  const { connect, isPending } = useConnect()
  const { disconnect } = useDisconnect()

  if (isConnected && address) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div
          style={{
            background: '#0f0f0f',
            border: '1px solid #1a1a2e',
            padding: '6px 12px',
            fontFamily: 'monospace',
            fontSize: '12px',
            color: '#00ff9d',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Wallet size={14} />
          {address.slice(0, 6)}...{address.slice(-4)}
        </div>
        <button
          onClick={() => disconnect()}
          style={{
            background: 'transparent',
            border: '1px solid #ef4444',
            color: '#ef4444',
            padding: '6px 10px',
            fontFamily: 'monospace',
            fontSize: '12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <LogOut size={14} />
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={() => connect({ connector: injected() })}
      disabled={isPending}
      style={{
        background: '#f59e0b',
        color: '#0a0a0a',
        border: 'none',
        padding: '8px 16px',
        fontFamily: 'monospace',
        fontSize: '11px',
        fontWeight: 'bold',
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        cursor: isPending ? 'wait' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        opacity: isPending ? 0.7 : 1,
      }}
    >
      <Wallet size={14} />
      {isPending ? 'CONNECTING...' : 'CONNECT'}
    </button>
  )
}
