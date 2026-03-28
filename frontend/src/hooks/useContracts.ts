'use client'

import { useReadContract, useWriteContract, useAccount, useWaitForTransactionReceipt } from 'wagmi'
import { NEXUS_RISK_ORACLE_ABI, PROTECTION_VAULT_ABI, CONTRACTS, BACKEND_URL } from '@/lib/contracts'
import { useMemo, useCallback } from 'react'
import type { RiskLevel } from '@/types'

// Get addresses from CONTRACTS object
const ORACLE_ADDRESS = CONTRACTS.ORACLE.address as `0x${string}`
const VAULT_ADDRESS = CONTRACTS.VAULT.address as `0x${string}`

// ═══════════════════════════════════════════════════════════════════════════
//                           RISK ORACLE HOOKS
// ═══════════════════════════════════════════════════════════════════════════

export function useProtocolRisk(protocolId: `0x${string}` | undefined) {
  const { data, isLoading, error, refetch } = useReadContract({
    address: ORACLE_ADDRESS,
    abi: NEXUS_RISK_ORACLE_ABI,
    functionName: 'getRiskScore',
    args: protocolId ? [protocolId] : undefined,
    query: { enabled: !!protocolId },
  })

  const risk = useMemo(() => {
    if (!data) return null
    const [score, timestamp] = data as [bigint, bigint]
    return {
      score: Number(score),
      timestamp: Number(timestamp),
      confidence: 100, // Not used in new contract
    }
  }, [data])

  return { risk, isLoading, error, refetch }
}

export function useHighRiskProtocols() {
  const { data, isLoading, error, refetch } = useReadContract({
    address: ORACLE_ADDRESS,
    abi: NEXUS_RISK_ORACLE_ABI,
    functionName: 'getHighRiskProtocols',
  })

  return {
    protocols: data as `0x${string}`[] | undefined,
    isLoading,
    error,
    refetch,
  }
}

export function useRiskThreshold() {
  // Threshold is now stored in config, not on-chain
  return {
    threshold: 70, // Default threshold
    isLoading: false,
    error: null,
  }
}

// ═══════════════════════════════════════════════════════════════════════════
//                         PROTECTION VAULT HOOKS
// ═══════════════════════════════════════════════════════════════════════════

export function useUserBalance(token: `0x${string}` | undefined) {
  const { address } = useAccount()

  const { data, isLoading, error, refetch } = useReadContract({
    address: VAULT_ADDRESS,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getUserBalance',
    args: address && token ? [address, token] : undefined,
    query: { enabled: !!address && !!token },
  })

  return {
    balance: data as bigint | undefined,
    isLoading,
    error,
    refetch,
  }
}

export function useUserRules() {
  const { address } = useAccount()

  const { data, isLoading, error, refetch } = useReadContract({
    address: VAULT_ADDRESS,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getUserRules',
    args: address ? [address] : undefined,
    query: { enabled: !!address },
  })

  return {
    ruleIds: data as bigint[] | undefined,
    isLoading,
    error,
    refetch,
  }
}

export function useProtectionRule(ruleId: bigint | undefined) {
  const { data, isLoading, error } = useReadContract({
    address: VAULT_ADDRESS,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getRule',
    args: ruleId !== undefined ? [ruleId] : undefined,
    query: { enabled: ruleId !== undefined },
  })

  const rule = useMemo(() => {
    if (!data) return null
    const [protocolId, riskThreshold, token, safeAddress, active] = data as [
      `0x${string}`,
      bigint,
      `0x${string}`,
      `0x${string}`,
      boolean
    ]
    return {
      protocolId,
      riskThreshold: Number(riskThreshold) / 100,
      token,
      safeAddress,
      active,
    }
  }, [data])

  return { rule, isLoading, error }
}

// ═══════════════════════════════════════════════════════════════════════════
//                         WRITE HOOKS (MUTATIONS)
// ═══════════════════════════════════════════════════════════════════════════

export function useDeposit() {
  const { writeContract, data: hash, isPending, error } = useWriteContract()
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash })

  const deposit = useCallback((token: `0x${string}`, amount: bigint) => {
    writeContract({
      address: VAULT_ADDRESS,
      abi: PROTECTION_VAULT_ABI,
      functionName: 'deposit',
      args: [token, amount],
    })
  }, [writeContract])

  return {
    deposit,
    isPending,
    isConfirming,
    isSuccess,
    error,
    hash,
  }
}

export function useWithdraw() {
  const { writeContract, data: hash, isPending, error } = useWriteContract()
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash })

  const withdraw = useCallback((token: `0x${string}`, amount: bigint) => {
    writeContract({
      address: VAULT_ADDRESS,
      abi: PROTECTION_VAULT_ABI,
      functionName: 'withdraw',
      args: [token, amount],
    })
  }, [writeContract])

  return {
    withdraw,
    isPending,
    isConfirming,
    isSuccess,
    error,
    hash,
  }
}

export function useSetProtectionRule() {
  const { writeContract, data: hash, isPending, error } = useWriteContract()
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash })

  const setRule = useCallback(
    (protocolId: `0x${string}`, threshold: number, token: `0x${string}`, safeAddress: `0x${string}`) => {
      writeContract({
        address: VAULT_ADDRESS,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'setProtectionRule',
        args: [protocolId, BigInt(Math.round(threshold * 100)), token, safeAddress],
      })
    },
    [writeContract]
  )

  return {
    setRule,
    isPending,
    isConfirming,
    isSuccess,
    error,
    hash,
  }
}

export function useRemoveProtectionRule() {
  const { writeContract, data: hash, isPending, error } = useWriteContract()
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash })

  const removeRule = useCallback((ruleId: bigint) => {
    writeContract({
      address: VAULT_ADDRESS,
      abi: PROTECTION_VAULT_ABI,
      functionName: 'removeProtectionRule',
      args: [ruleId],
    })
  }, [writeContract])

  return {
    removeRule,
    isPending,
    isConfirming,
    isSuccess,
    error,
    hash,
  }
}

// ═══════════════════════════════════════════════════════════════════════════
//                              UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

export function encodeProtocolId(slug: string): `0x${string}` {
  // Simple keccak256-like encoding (use viem's keccak256 in production)
  const hex = Array.from(slug)
    .map(c => c.charCodeAt(0).toString(16).padStart(2, '0'))
    .join('')
    .padEnd(64, '0')
  return `0x${hex}` as `0x${string}`
}

export function getRiskLevel(score: number): RiskLevel {
  if (score >= 70) return 'CRITICAL'
  if (score >= 55) return 'HIGH'
  if (score >= 40) return 'MEDIUM'
  return 'LOW'
}

export function getRiskColor(score: number): string {
  if (score >= 70) return '#ef4444'
  if (score >= 55) return '#f59e0b'
  if (score >= 40) return '#eab308'
  return '#00ff9d'
}
