'use client'

import { useReadContract, useWriteContract, useWatchContractEvent } from 'wagmi'
import { keccak256, toBytes, formatUnits } from 'viem'
import { useCallback, useState } from 'react'
import {
  CONTRACTS,
  NEXUS_ORACLE_ABI,
  PROTECTION_VAULT_ABI,
  ERC20_ABI,
  type ProtectionRule,
  type RiskScore,
} from '@/lib/contracts'

// ═══════════════════════════════════════════════════════════════════════════
//                           UTILITY
// ═══════════════════════════════════════════════════════════════════════════

export function toProtocolId(name: string): `0x${string}` {
  return keccak256(toBytes(name))
}

export function formatRiskScore(score: bigint): number {
  return Number(score)
}

export function getRiskLevel(score: number): 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' {
  if (score >= 80) return 'CRITICAL'
  if (score >= 70) return 'HIGH'
  if (score >= 50) return 'MEDIUM'
  return 'LOW'
}

export function getRiskColor(score: number): string {
  if (score >= 80) return '#ef4444'
  if (score >= 70) return '#f59e0b'
  if (score >= 50) return '#eab308'
  return '#00ff9d'
}

// ═══════════════════════════════════════════════════════════════════════════
//                         ORACLE HOOKS
// ═══════════════════════════════════════════════════════════════════════════

export function useRiskScore(protocolName: string) {
  const protocolId = toProtocolId(protocolName)

  return useReadContract({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    functionName: 'getRiskScore',
    args: [protocolId],
    query: {
      refetchInterval: 30_000,
      enabled: !!protocolName,
    },
  })
}

export function useRiskScoreById(protocolId: `0x${string}`) {
  return useReadContract({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    functionName: 'getRiskScore',
    args: [protocolId],
    query: {
      refetchInterval: 30_000,
    },
  })
}

export function useHighRiskProtocols() {
  return useReadContract({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    functionName: 'getHighRiskProtocols',
    query: {
      refetchInterval: 30_000,
    },
  })
}

export function useProtocolCount() {
  return useReadContract({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    functionName: 'getProtocolCount',
    query: {
      refetchInterval: 60_000,
    },
  })
}

export function useAlertThreshold() {
  return useReadContract({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    functionName: 'alertThreshold',
  })
}

export function useProtocolName(protocolId: `0x${string}`) {
  return useReadContract({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    functionName: 'protocolNames',
    args: [protocolId],
    query: {
      enabled: !!protocolId && protocolId !== '0x0000000000000000000000000000000000000000000000000000000000000000',
    },
  })
}

// ═══════════════════════════════════════════════════════════════════════════
//                          VAULT HOOKS
// ═══════════════════════════════════════════════════════════════════════════

export function useVaultBalance(
  userAddress: `0x${string}` | undefined,
  tokenAddress: `0x${string}`
) {
  return useReadContract({
    address: CONTRACTS.PROTECTION_VAULT,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getBalance',
    args: userAddress ? [userAddress, tokenAddress] : undefined,
    query: {
      enabled: !!userAddress && !!tokenAddress,
      refetchInterval: 30_000,
    },
  })
}

export function useUserRules(userAddress: `0x${string}` | undefined) {
  return useReadContract({
    address: CONTRACTS.PROTECTION_VAULT,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getRules',
    args: userAddress ? [userAddress] : undefined,
    query: {
      enabled: !!userAddress,
      refetchInterval: 30_000,
    },
  })
}

export function useRuleCount(userAddress: `0x${string}` | undefined) {
  return useReadContract({
    address: CONTRACTS.PROTECTION_VAULT,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getRuleCount',
    args: userAddress ? [userAddress] : undefined,
    query: {
      enabled: !!userAddress,
    },
  })
}

export function useHasVault(userAddress: `0x${string}` | undefined) {
  return useReadContract({
    address: CONTRACTS.PROTECTION_VAULT,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'hasVault',
    args: userAddress ? [userAddress] : undefined,
    query: {
      enabled: !!userAddress,
    },
  })
}

export function useTotalUsers() {
  return useReadContract({
    address: CONTRACTS.PROTECTION_VAULT,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getTotalUsers',
    query: {
      refetchInterval: 60_000,
    },
  })
}

// ═══════════════════════════════════════════════════════════════════════════
//                        WRITE HOOKS
// ═══════════════════════════════════════════════════════════════════════════

export function useDeposit() {
  const { writeContract, isPending, isSuccess, error, data: hash } = useWriteContract()

  const deposit = useCallback(
    (tokenAddress: `0x${string}`, amount: bigint) => {
      writeContract({
        address: CONTRACTS.PROTECTION_VAULT,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'deposit',
        args: [tokenAddress, amount],
      })
    },
    [writeContract]
  )

  return { deposit, isPending, isSuccess, error, hash }
}

export function useWithdraw() {
  const { writeContract, isPending, isSuccess, error, data: hash } = useWriteContract()

  const withdraw = useCallback(
    (tokenAddress: `0x${string}`, amount: bigint) => {
      writeContract({
        address: CONTRACTS.PROTECTION_VAULT,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'withdraw',
        args: [tokenAddress, amount],
      })
    },
    [writeContract]
  )

  return { withdraw, isPending, isSuccess, error, hash }
}

export function useAddProtectionRule() {
  const { writeContract, isPending, isSuccess, error, data: hash } = useWriteContract()

  const addRule = useCallback(
    (
      protocolName: string,
      threshold: number,
      tokenAddress: `0x${string}`,
      safeAddress: `0x${string}`
    ) => {
      writeContract({
        address: CONTRACTS.PROTECTION_VAULT,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'addProtectionRuleByName',
        args: [protocolName, BigInt(threshold), tokenAddress, safeAddress],
      })
    },
    [writeContract]
  )

  return { addRule, isPending, isSuccess, error, hash }
}

export function useDeactivateRule() {
  const { writeContract, isPending, isSuccess, error, data: hash } = useWriteContract()

  const deactivateRule = useCallback(
    (ruleIndex: number) => {
      writeContract({
        address: CONTRACTS.PROTECTION_VAULT,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'deactivateRule',
        args: [BigInt(ruleIndex)],
      })
    },
    [writeContract]
  )

  return { deactivateRule, isPending, isSuccess, error, hash }
}

export function useApproveToken(tokenAddress: `0x${string}`) {
  const { writeContract, isPending, isSuccess, error, data: hash } = useWriteContract()

  const approve = useCallback(
    (amount: bigint) => {
      writeContract({
        address: tokenAddress,
        abi: ERC20_ABI,
        functionName: 'approve',
        args: [CONTRACTS.PROTECTION_VAULT, amount],
      })
    },
    [writeContract, tokenAddress]
  )

  return { approve, isPending, isSuccess, error, hash }
}

// ═══════════════════════════════════════════════════════════════════════════
//                          EVENT HOOKS
// ═══════════════════════════════════════════════════════════════════════════

export interface HighRiskAlertEvent {
  protocolId: `0x${string}`
  riskScore: bigint
  timestamp: bigint
}

export function useHighRiskAlerts(onAlert: (event: HighRiskAlertEvent) => void) {
  useWatchContractEvent({
    address: CONTRACTS.NEXUS_ORACLE,
    abi: NEXUS_ORACLE_ABI,
    eventName: 'HighRiskAlert',
    onLogs: (logs) => {
      logs.forEach((log) => {
        const args = log.args as unknown as HighRiskAlertEvent
        if (args) {
          onAlert(args)
        }
      })
    },
  })
}

export interface ProtectionTriggeredEvent {
  user: `0x${string}`
  protocolId: `0x${string}`
  riskScore: bigint
  token: `0x${string}`
  amount: bigint
  safeAddress: `0x${string}`
}

export function useProtectionTriggeredEvents(
  userAddress: `0x${string}` | undefined,
  onTriggered: (event: ProtectionTriggeredEvent) => void
) {
  useWatchContractEvent({
    address: CONTRACTS.PROTECTION_VAULT,
    abi: PROTECTION_VAULT_ABI,
    eventName: 'ProtectionTriggered',
    onLogs: (logs) => {
      logs.forEach((log) => {
        const args = log.args as unknown as ProtectionTriggeredEvent
        if (args && (!userAddress || args.user.toLowerCase() === userAddress.toLowerCase())) {
          onTriggered(args)
        }
      })
    },
  })
}

// ═══════════════════════════════════════════════════════════════════════════
//                      TOKEN BALANCE HOOK
// ═══════════════════════════════════════════════════════════════════════════

export function useTokenBalance(
  tokenAddress: `0x${string}`,
  userAddress: `0x${string}` | undefined
) {
  return useReadContract({
    address: tokenAddress,
    abi: ERC20_ABI,
    functionName: 'balanceOf',
    args: userAddress ? [userAddress] : undefined,
    query: {
      enabled: !!userAddress && !!tokenAddress,
      refetchInterval: 30_000,
    },
  })
}

export function useTokenAllowance(
  tokenAddress: `0x${string}`,
  ownerAddress: `0x${string}` | undefined
) {
  return useReadContract({
    address: tokenAddress,
    abi: ERC20_ABI,
    functionName: 'allowance',
    args: ownerAddress ? [ownerAddress, CONTRACTS.PROTECTION_VAULT] : undefined,
    query: {
      enabled: !!ownerAddress && !!tokenAddress,
      refetchInterval: 10_000,
    },
  })
}
