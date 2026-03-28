/**
 * useProtectionVault Hook - Real vault interactions
 * Handles deposits, withdrawals, and protection rules
 */
import { useState, useEffect } from 'react'
import { useAccount, useWriteContract, useReadContract, useWaitForTransactionReceipt } from 'wagmi'
import { parseEther, formatEther } from 'viem'
import { CONTRACTS, PROTECTION_VAULT_ABI } from '@/lib/contracts'

// Zero address for native ETH
const NATIVE_TOKEN = '0x0000000000000000000000000000000000000000' as const

export interface UserBalance {
  balance: bigint
  formatted: string
}

export interface ProtectionRule {
  protocolId: string
  threshold: number
  safeAddress: string
  active: boolean
}

export function useProtectionVault() {
  const { address } = useAccount()
  const [isTransacting, setIsTransacting] = useState(false)
  
  const { writeContract, data: txHash, error: writeError } = useWriteContract()
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({
    hash: txHash,
  })

  // Get user balance
  const { data: balanceData, refetch: refetchBalance } = useReadContract({
    address: CONTRACTS.VAULT.address as `0x${string}`,
    abi: PROTECTION_VAULT_ABI,
    functionName: 'getUserBalance',
    args: address ? [address, NATIVE_TOKEN] : undefined,
    chainId: CONTRACTS.VAULT.chainId,
  })

  const userBalance: UserBalance = {
    balance: balanceData || BigInt(0),
    formatted: formatEther(balanceData || BigInt(0))
  }

  // Deposit tokens to vault
  const deposit = async (amountEth: string) => {
    if (!address || !writeContract) return

    try {
      setIsTransacting(true)
      const amount = parseEther(amountEth)
      
      writeContract({
        address: CONTRACTS.VAULT.address as `0x${string}`,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'deposit',
        args: [NATIVE_TOKEN, amount],
        chainId: CONTRACTS.VAULT.chainId,
      })

    } catch (error) {
      console.error('Deposit failed:', error)
      setIsTransacting(false)
    }
  }

  // Withdraw ETH from vault
  const withdraw = async (amountEth: string) => {
    if (!address || !writeContract) return

    try {
      setIsTransacting(true)
      
      writeContract({
        address: CONTRACTS.VAULT.address as `0x${string}`,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'withdraw',
        args: [NATIVE_TOKEN, parseEther(amountEth)],
        chainId: CONTRACTS.VAULT.chainId,
      })

    } catch (error) {
      console.error('Withdraw failed:', error)
      setIsTransacting(false)
    }
  }

  // Add protection rule
  const addProtectionRule = async (
    protocolId: `0x${string}`,
    threshold: number,
    safeAddress: `0x${string}`
  ) => {
    if (!address || !writeContract) return

    try {
      setIsTransacting(true)
      
      writeContract({
        address: CONTRACTS.VAULT.address as `0x${string}`,
        abi: PROTECTION_VAULT_ABI,
        functionName: 'setProtectionRule',
        args: [protocolId, BigInt(threshold), NATIVE_TOKEN, safeAddress],
        chainId: CONTRACTS.VAULT.chainId,
      })

    } catch (error) {
      console.error('Add protection rule failed:', error)
      setIsTransacting(false)
    }
  }

  // Reset transaction state when tx is confirmed
  useEffect(() => {
    if (isSuccess && isTransacting) {
      setIsTransacting(false)
      refetchBalance()
    }
  }, [isSuccess, isTransacting, refetchBalance])

  return {
    // State
    userBalance,
    isTransacting: isTransacting || isConfirming,
    txHash,
    error: writeError,
    
    // Actions
    deposit,
    withdraw,
    addProtectionRule,
    refetchBalance,
  }
}