'use client'

import { useState } from 'react'
import { useAccount } from 'wagmi'
import { parseUnits, formatUnits } from 'viem'
import {
  useVaultBalance,
  useUserRules,
  useHasVault,
  useDeposit,
  useWithdraw,
  useAddProtectionRule,
  useDeactivateRule,
  useApproveToken,
  useTokenBalance,
  useTokenAllowance,
  getRiskColor,
  toProtocolId,
} from '@/hooks/useNexus'
import { CONTRACTS } from '@/lib/contracts'

// Supported tokens
const TOKENS = [
  { symbol: 'USDC', address: '0x0000000000000000000000000000000000000001' as `0x${string}`, decimals: 6 },
  { symbol: 'USDT', address: '0x0000000000000000000000000000000000000002' as `0x${string}`, decimals: 6 },
  { symbol: 'DAI', address: '0x0000000000000000000000000000000000000003' as `0x${string}`, decimals: 18 },
]

// Available protocols
const PROTOCOLS = [
  'Lido', 'Aave V3', 'EigenLayer', 'ether.fi', 'Ethena',
  'Uniswap V3', 'Maker', 'Pendle', 'Compound V3', 'Morpho',
]

export default function ProtectionPage() {
  const { address, isConnected } = useAccount()

  // Tab state
  const [activeTab, setActiveTab] = useState<'deposit' | 'rules'>('deposit')

  // Form states
  const [depositAmount, setDepositAmount] = useState('')
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [selectedToken, setSelectedToken] = useState(TOKENS[0])
  const [newRule, setNewRule] = useState({ protocol: PROTOCOLS[0], threshold: 70, safeAddress: '' })

  // Contract hooks
  const { data: hasVault } = useHasVault(address)
  const { data: vaultBalance } = useVaultBalance(address, selectedToken.address)
  const { data: rules } = useUserRules(address)
  const { data: tokenBalance } = useTokenBalance(selectedToken.address, address)
  const { data: allowance } = useTokenAllowance(selectedToken.address, address)

  const { deposit, isPending: isDepositing } = useDeposit()
  const { withdraw, isPending: isWithdrawing } = useWithdraw()
  const { addRule, isPending: isAddingRule } = useAddProtectionRule()
  const { deactivateRule, isPending: isDeactivating } = useDeactivateRule()
  const { approve, isPending: isApproving } = useApproveToken(selectedToken.address)

  const needsApproval = (): boolean => {
    if (!depositAmount || !allowance) return false
    const amt = parseUnits(depositAmount, selectedToken.decimals)
    return allowance < amt
  }

  const handleDeposit = () => {
    if (!depositAmount) return
    const amt = parseUnits(depositAmount, selectedToken.decimals)
    deposit(selectedToken.address, amt)
  }

  const handleWithdraw = () => {
    if (!withdrawAmount) return
    const amt = parseUnits(withdrawAmount, selectedToken.decimals)
    withdraw(selectedToken.address, amt)
  }

  const handleApprove = () => {
    if (!depositAmount) return
    const amt = parseUnits(depositAmount, selectedToken.decimals)
    approve(amt)
  }

  const handleAddRule = () => {
    if (!newRule.safeAddress) return
    addRule(newRule.protocol, newRule.threshold, selectedToken.address, newRule.safeAddress as `0x${string}`)
  }

  if (!isConnected) {
    return (
      <div style={{ minHeight: 'calc(100vh - 48px)', background: '#0a0a0a', padding: '80px 24px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '14px', marginBottom: '16px' }}>
            // Connect wallet to access protection vault
          </div>
          <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '24px' }}>
            WALLET NOT CONNECTED
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', background: '#0a0a0a', padding: '80px 24px' }}>
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ color: '#00ff9d', fontFamily: 'monospace', fontSize: '14px', marginBottom: '8px' }}>
            {'>'} MY PROTECTION
          </div>
          <h1 style={{ fontFamily: 'monospace', fontSize: '36px', color: '#e2e8f0', margin: 0 }}>
            Protection Vault
          </h1>
          <p style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '13px', marginTop: '8px' }}>
            // Deposit tokens and set up autonomous protection rules
          </p>
        </div>

        {/* Vault Status */}
        <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '20px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: hasVault ? '#00ff9d' : '#64748b',
            }} />
            <span style={{ color: hasVault ? '#00ff9d' : '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.15em' }}>
              {hasVault ? 'VAULT ACTIVE' : 'NO VAULT'}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
            {[
              { label: 'Vault Balance', value: vaultBalance ? formatUnits(vaultBalance, selectedToken.decimals) : '0', suffix: selectedToken.symbol },
              { label: 'Active Rules', value: rules?.filter(r => (r.flags & 1) === 1).length?.toString() ?? '0', suffix: '' },
              { label: 'Wallet Balance', value: tokenBalance ? formatUnits(tokenBalance, selectedToken.decimals) : '0', suffix: selectedToken.symbol },
            ].map(s => (
              <div key={s.label}>
                <div style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '4px' }}>
                  {s.label}
                </div>
                <div style={{ color: '#00ff9d', fontFamily: 'monospace', fontSize: '24px', fontWeight: 'bold' }}>
                  {parseFloat(s.value).toFixed(2)} <span style={{ fontSize: '14px', color: '#64748b' }}>{s.suffix}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
          {(['deposit', 'rules'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: activeTab === tab ? '#1a1a2e' : 'transparent',
                border: `1px solid ${activeTab === tab ? '#7c3aed' : '#1a1a2e'}`,
                color: activeTab === tab ? '#e2e8f0' : '#64748b',
                padding: '10px 20px',
                fontFamily: 'monospace',
                fontSize: '12px',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                cursor: 'pointer',
              }}
            >
              {tab === 'deposit' ? 'DEPOSIT / WITHDRAW' : 'PROTECTION RULES'}
            </button>
          ))}
        </div>

        {activeTab === 'deposit' ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            {/* Deposit */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '24px' }}>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px', fontWeight: 'bold', marginBottom: '20px' }}>
                DEPOSIT
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', display: 'block', marginBottom: '8px' }}>
                  Token
                </label>
                <select
                  value={selectedToken.symbol}
                  onChange={(e) => setSelectedToken(TOKENS.find(t => t.symbol === e.target.value) ?? TOKENS[0])}
                  style={{
                    width: '100%',
                    background: '#0a0a0a',
                    border: '1px solid #1a1a2e',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                  }}
                >
                  {TOKENS.map(t => <option key={t.symbol} value={t.symbol}>{t.symbol}</option>)}
                </select>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', display: 'block', marginBottom: '8px' }}>
                  Amount
                </label>
                <input
                  type="number"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  placeholder="0.00"
                  style={{
                    width: '100%',
                    background: '#0a0a0a',
                    border: '1px solid #1a1a2e',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                  }}
                />
              </div>

              {needsApproval() ? (
                <button
                  onClick={handleApprove}
                  disabled={isApproving}
                  style={{
                    width: '100%',
                    background: '#7c3aed',
                    border: 'none',
                    color: '#fff',
                    padding: '14px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    cursor: isApproving ? 'wait' : 'pointer',
                    opacity: isApproving ? 0.7 : 1,
                  }}
                >
                  {isApproving ? 'APPROVING...' : 'APPROVE'}
                </button>
              ) : (
                <button
                  onClick={handleDeposit}
                  disabled={isDepositing || !depositAmount}
                  style={{
                    width: '100%',
                    background: '#00ff9d',
                    border: 'none',
                    color: '#0a0a0a',
                    padding: '14px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    cursor: isDepositing ? 'wait' : 'pointer',
                    opacity: isDepositing || !depositAmount ? 0.7 : 1,
                  }}
                >
                  {isDepositing ? 'DEPOSITING...' : 'DEPOSIT'}
                </button>
              )}
            </div>

            {/* Withdraw */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '24px' }}>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px', fontWeight: 'bold', marginBottom: '20px' }}>
                WITHDRAW
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', display: 'block', marginBottom: '8px' }}>
                  Amount
                </label>
                <input
                  type="number"
                  value={withdrawAmount}
                  onChange={(e) => setWithdrawAmount(e.target.value)}
                  placeholder="0.00"
                  style={{
                    width: '100%',
                    background: '#0a0a0a',
                    border: '1px solid #1a1a2e',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                  }}
                />
              </div>

              <button
                onClick={handleWithdraw}
                disabled={isWithdrawing || !withdrawAmount}
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: '1px solid #ef4444',
                  color: '#ef4444',
                  padding: '14px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  cursor: isWithdrawing ? 'wait' : 'pointer',
                  opacity: isWithdrawing || !withdrawAmount ? 0.7 : 1,
                  marginTop: '64px',
                }}
              >
                {isWithdrawing ? 'WITHDRAWING...' : 'WITHDRAW'}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            {/* Add Rule */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '24px' }}>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px', fontWeight: 'bold', marginBottom: '20px' }}>
                ADD RULE
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', display: 'block', marginBottom: '8px' }}>
                  Protocol to Monitor
                </label>
                <select
                  value={newRule.protocol}
                  onChange={(e) => setNewRule({ ...newRule, protocol: e.target.value })}
                  style={{
                    width: '100%',
                    background: '#0a0a0a',
                    border: '1px solid #1a1a2e',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                  }}
                >
                  {PROTOCOLS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', display: 'block', marginBottom: '8px' }}>
                  Threshold ({newRule.threshold})
                </label>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={newRule.threshold}
                  onChange={(e) => setNewRule({ ...newRule, threshold: parseInt(e.target.value) })}
                  style={{ width: '100%' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#64748b', marginTop: '4px' }}>
                  <span>1</span>
                  <span style={{ color: getRiskColor(newRule.threshold) }}>{newRule.threshold}</span>
                  <span>100</span>
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ color: '#64748b', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', display: 'block', marginBottom: '8px' }}>
                  Safe Address
                </label>
                <input
                  type="text"
                  value={newRule.safeAddress}
                  onChange={(e) => setNewRule({ ...newRule, safeAddress: e.target.value })}
                  placeholder="0x..."
                  style={{
                    width: '100%',
                    background: '#0a0a0a',
                    border: '1px solid #1a1a2e',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                  }}
                />
              </div>

              <button
                onClick={handleAddRule}
                disabled={isAddingRule || !newRule.safeAddress || !hasVault}
                style={{
                  width: '100%',
                  background: '#7c3aed',
                  border: 'none',
                  color: '#fff',
                  padding: '14px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  cursor: isAddingRule ? 'wait' : 'pointer',
                  opacity: isAddingRule || !newRule.safeAddress || !hasVault ? 0.7 : 1,
                }}
              >
                {isAddingRule ? 'ADDING...' : 'ADD RULE'}
              </button>

              {!hasVault && (
                <div style={{ color: '#f59e0b', fontSize: '11px', marginTop: '12px', fontFamily: 'monospace' }}>
                  ⚠ Deposit tokens first to create a vault
                </div>
              )}
            </div>

            {/* Active Rules */}
            <div style={{ background: '#0f0f0f', border: '1px solid #1a1a2e', padding: '24px' }}>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '14px', fontWeight: 'bold', marginBottom: '20px' }}>
                ACTIVE RULES ({rules?.filter(r => (r.flags & 1) === 1).length ?? 0})
              </div>

              {(!rules || rules.length === 0) ? (
                <div style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '12px', textAlign: 'center', padding: '40px 0' }}>
                  No protection rules configured
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {rules.map((rule, i) => (
                    <div
                      key={i}
                      style={{
                        background: '#0a0a0a',
                        border: `1px solid ${(rule.flags & 1) === 1 ? '#1a1a2e' : '#374151'}`,
                        padding: '12px',
                        opacity: (rule.flags & 1) === 1 ? 1 : 0.5,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px', fontWeight: 'bold' }}>
                          #{i + 1}
                        </span>
                        {(rule.flags & 1) === 1 && (
                          <button
                            onClick={() => deactivateRule(i)}
                            disabled={isDeactivating}
                            style={{
                              background: 'transparent',
                              border: '1px solid #ef4444',
                              color: '#ef4444',
                              padding: '4px 8px',
                              fontFamily: 'monospace',
                              fontSize: '9px',
                              cursor: 'pointer',
                            }}
                          >
                            DEACTIVATE
                          </button>
                        )}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace', fontSize: '11px', marginBottom: '4px' }}>
                        <span style={{ color: '#64748b' }}>Threshold</span>
                        <span style={{ color: getRiskColor(Number(rule.riskThreshold)) }}>{Number(rule.riskThreshold)}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace', fontSize: '11px' }}>
                        <span style={{ color: '#64748b' }}>Safe</span>
                        <span style={{ color: '#e2e8f0' }}>{rule.safeAddress.slice(0, 8)}...{rule.safeAddress.slice(-6)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
