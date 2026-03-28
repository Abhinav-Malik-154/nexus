/**
 * useNexusOracle Hook - Read live data from deployed Oracle contract
 * NO FAKE DATA - connects to actual blockchain
 */
import { useReadContract, useReadContracts } from 'wagmi'
import { CONTRACTS, NEXUS_RISK_ORACLE_ABI } from '@/lib/contracts'
import { keccak256, toBytes } from 'viem'

export interface OracleData {
  score: number
  timestamp: number
  lastUpdated: string
  isStale: boolean
}

export interface ProtocolRisk {
  protocol: string
  riskScore: number
  timestamp: number
  isHigh: boolean
  lastUpdated: string
}

// Convert protocol name to bytes32 ID (same as backend)
function protocolNameToId(name: string): `0x${string}` {
  return keccak256(toBytes(name.toLowerCase()))
}

export function useNexusOracle() {
  // Get high risk protocols
  const { data: highRiskProtocols, isLoading: loadingHighRisk } = useReadContract({
    address: CONTRACTS.ORACLE.address,
    abi: NEXUS_RISK_ORACLE_ABI,
    functionName: 'getHighRiskProtocols',
    chainId: CONTRACTS.ORACLE.chainId,
  })

  return {
    highRiskProtocols: highRiskProtocols || [],
    loadingHighRisk,
    protocolNameToId,
  }
}

export function useProtocolRisk(protocolName: string) {
  const protocolId = protocolNameToId(protocolName)
  
  const { data, isLoading, error, refetch } = useReadContract({
    address: CONTRACTS.ORACLE.address,
    abi: NEXUS_RISK_ORACLE_ABI,
    functionName: 'getRiskScore',
    args: [protocolId],
    chainId: CONTRACTS.ORACLE.chainId,
  })

  const oracleData: OracleData | null = data ? {
    score: Number(data[0]), // uint64 score
    timestamp: Number(data[1]), // uint256 timestamp
    lastUpdated: data[1] > 0 ? new Date(Number(data[1]) * 1000).toISOString() : 'never',
    isStale: data[1] > 0 ? Date.now() - (Number(data[1]) * 1000) > 3600000 : true // >1 hour stale
  } : null

  return {
    data: oracleData,
    isLoading,
    error,
    refetch,
  }
}

export function useMultipleProtocolRisks(protocolNames: string[]) {
  const contracts = protocolNames.map(name => ({
    address: CONTRACTS.ORACLE.address,
    abi: NEXUS_RISK_ORACLE_ABI,
    functionName: 'getRiskScore',
    args: [protocolNameToId(name)],
    chainId: CONTRACTS.ORACLE.chainId,
  }))

  const { data, isLoading, error } = useReadContracts({
    contracts,
  })

  const protocolRisks: ProtocolRisk[] = protocolNames.map((protocol, index) => {
    const result = data?.[index]
    const hasData = result?.status === 'success' && result.result
    
    return {
      protocol,
      riskScore: hasData ? Number(result.result[0]) : 0,
      timestamp: hasData ? Number(result.result[1]) : 0,
      isHigh: hasData ? Number(result.result[0]) > 70 : false,
      lastUpdated: hasData && Number(result.result[1]) > 0 
        ? new Date(Number(result.result[1]) * 1000).toISOString() 
        : 'never'
    }
  })

  return {
    protocolRisks,
    isLoading,
    error,
  }
}