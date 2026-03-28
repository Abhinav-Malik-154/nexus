// Contract Configuration - Real deployed addresses
export const CONTRACTS = {
  ORACLE: {
    address: "0x30BB8531e998A3c6574C8985e9c360d621493595" as const,
    chainId: 80002, // Polygon Amoy testnet
  },
  VAULT: {
    address: "0x7E86F2eF483a5B43d8f6d41a88EeeFE7ED745CdC" as const,
    chainId: 80002,
  },
} as const;

// Backend URL
export const BACKEND_URL = process.env.NODE_ENV === 'production' 
  ? 'https://your-backend-url.com'
  : 'http://localhost:8000';

// Updated Oracle ABI to match deployed contract

export const NEXUS_RISK_ORACLE_ABI = [
  {
    name: 'getRiskScore',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'protocolId', type: 'bytes32' }],
    outputs: [
      { name: 'score', type: 'uint64' },
      { name: 'timestamp', type: 'uint256' }
    ],
  },
  {
    name: 'getHighRiskProtocols',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'bytes32[]' }],
  },
  {
    name: 'updateRiskScore',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'protocolId', type: 'bytes32' },
      { name: 'score', type: 'uint64' }
    ],
    outputs: [],
  }
] as const

export const PROTECTION_VAULT_ABI = [
  {
    name: 'deposit',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'token', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [],
  },
  {
    name: 'withdraw',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'token', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [],
  },
  {
    name: 'setProtectionRule',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'protocolId', type: 'bytes32' },
      { name: 'riskThreshold', type: 'uint256' },
      { name: 'token', type: 'address' },
      { name: 'safeAddress', type: 'address' },
    ],
    outputs: [{ name: 'ruleId', type: 'uint256' }],
  },
  {
    name: 'removeProtectionRule',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [{ name: 'ruleId', type: 'uint256' }],
    outputs: [],
  },
  {
    name: 'getUserRules',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'user', type: 'address' }],
    outputs: [{ name: '', type: 'uint256[]' }],
  },
  {
    name: 'getRule',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'ruleId', type: 'uint256' }],
    outputs: [
      { name: 'protocolId', type: 'bytes32' },
      { name: 'riskThreshold', type: 'uint256' },
      { name: 'token', type: 'address' },
      { name: 'safeAddress', type: 'address' },
      { name: 'active', type: 'bool' },
    ],
  },
  {
    name: 'getUserBalance',
    type: 'function',
    stateMutability: 'view',
    inputs: [
      { name: 'user', type: 'address' },
      { name: 'token', type: 'address' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'checkUpkeep',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'checkData', type: 'bytes' }],
    outputs: [
      { name: 'upkeepNeeded', type: 'bool' },
      { name: 'performData', type: 'bytes' },
    ],
  },
  {
    name: 'performUpkeep',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [{ name: 'performData', type: 'bytes' }],
    outputs: [],
  },
  {
    name: 'ProtectionTriggered',
    type: 'event',
    inputs: [
      { name: 'user', type: 'address', indexed: true },
      { name: 'ruleId', type: 'uint256', indexed: true },
      { name: 'protocolId', type: 'bytes32', indexed: true },
      { name: 'token', type: 'address', indexed: false },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
  {
    name: 'Deposited',
    type: 'event',
    inputs: [
      { name: 'user', type: 'address', indexed: true },
      { name: 'token', type: 'address', indexed: true },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
  {
    name: 'Withdrawn',
    type: 'event',
    inputs: [
      { name: 'user', type: 'address', indexed: true },
      { name: 'token', type: 'address', indexed: true },
      { name: 'amount', type: 'uint256', indexed: false },
    ],
  },
] as const

// Default addresses (should be overridden by environment variables)
export const ORACLE_ADDRESS = (process.env.NEXT_PUBLIC_ORACLE_ADDRESS || '0x0000000000000000000000000000000000000000') as `0x${string}`
export const VAULT_ADDRESS = (process.env.NEXT_PUBLIC_VAULT_ADDRESS || '0x0000000000000000000000000000000000000000') as `0x${string}`
