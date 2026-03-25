/**
 * Nexus Protocol Contract Configuration
 *
 * Update CONTRACTS addresses after deployment to Polygon Amoy.
 * ABIs match the gas-optimized contract versions.
 */

// ═══════════════════════════════════════════════════════════════════════════
//                          CONTRACT ADDRESSES
// ═══════════════════════════════════════════════════════════════════════════

export const CONTRACTS = {
  // Update these after deployment
  NEXUS_ORACLE: '0xC0b6B479A264e0d900f6AE7c461668905a40AAb0' as `0x${string}`,
  PROTECTION_VAULT: '0x30F9dd5aFAbA8a3270c3351AD9aabca6CED391F3' as `0x${string}`,
} as const

// ═══════════════════════════════════════════════════════════════════════════
//                          NEXUS ORACLE ABI
// ═══════════════════════════════════════════════════════════════════════════

export const NEXUS_ORACLE_ABI = [
  // Read functions
  {
    name: 'getRiskScore',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'protocolId', type: 'bytes32' }],
    outputs: [
      { name: 'score', type: 'uint64' },
      { name: 'lastUpdated', type: 'uint64' },
      { name: 'isStale', type: 'bool' },
    ],
  },
  {
    name: 'getRiskScoreByName',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'protocolName', type: 'string' }],
    outputs: [
      { name: 'score', type: 'uint64' },
      { name: 'lastUpdated', type: 'uint64' },
      { name: 'isStale', type: 'bool' },
    ],
  },
  {
    name: 'getHighRiskProtocols',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: 'highRisk', type: 'bytes32[]' }],
  },
  {
    name: 'getProtocolCount',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'protocolIds',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'index', type: 'uint256' }],
    outputs: [{ name: '', type: 'bytes32' }],
  },
  {
    name: 'protocolNames',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'protocolId', type: 'bytes32' }],
    outputs: [{ name: '', type: 'string' }],
  },
  {
    name: 'alertThreshold',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'uint64' }],
  },
  {
    name: 'isTracked',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'protocolId', type: 'bytes32' }],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    name: 'toProtocolId',
    type: 'function',
    stateMutability: 'pure',
    inputs: [{ name: 'protocolName', type: 'string' }],
    outputs: [{ name: '', type: 'bytes32' }],
  },
  // Events
  {
    name: 'RiskScoreUpdated',
    type: 'event',
    inputs: [
      { name: 'protocolId', type: 'bytes32', indexed: true },
      { name: 'oldScore', type: 'uint64', indexed: false },
      { name: 'newScore', type: 'uint64', indexed: false },
      { name: 'timestamp', type: 'uint64', indexed: false },
    ],
  },
  {
    name: 'HighRiskAlert',
    type: 'event',
    inputs: [
      { name: 'protocolId', type: 'bytes32', indexed: true },
      { name: 'riskScore', type: 'uint64', indexed: false },
      { name: 'timestamp', type: 'uint64', indexed: false },
    ],
  },
] as const

// ═══════════════════════════════════════════════════════════════════════════
//                        PROTECTION VAULT ABI
// ═══════════════════════════════════════════════════════════════════════════

export const PROTECTION_VAULT_ABI = [
  // Write functions
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
    name: 'addProtectionRule',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'protocolId', type: 'bytes32' },
      { name: 'riskThreshold', type: 'uint64' },
      { name: 'token', type: 'address' },
      { name: 'safeAddress', type: 'address' },
    ],
    outputs: [],
  },
  {
    name: 'addProtectionRuleByName',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'protocolName', type: 'string' },
      { name: 'riskThreshold', type: 'uint64' },
      { name: 'token', type: 'address' },
      { name: 'safeAddress', type: 'address' },
    ],
    outputs: [],
  },
  {
    name: 'deactivateRule',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [{ name: 'ruleIndex', type: 'uint256' }],
    outputs: [],
  },
  // Read functions
  {
    name: 'getBalance',
    type: 'function',
    stateMutability: 'view',
    inputs: [
      { name: 'user', type: 'address' },
      { name: 'token', type: 'address' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'getRules',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'user', type: 'address' }],
    outputs: [
      {
        name: '',
        type: 'tuple[]',
        components: [
          { name: 'protocolId', type: 'bytes32' },
          { name: 'token', type: 'address' },
          { name: 'riskThreshold', type: 'uint64' },
          { name: 'flags', type: 'uint8' },
          { name: 'safeAddress', type: 'address' },
          { name: 'createdAt', type: 'uint64' },
        ],
      },
    ],
  },
  {
    name: 'getRuleCount',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'user', type: 'address' }],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'hasVault',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'user', type: 'address' }],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    name: 'getTotalUsers',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'uint256' }],
  },
  // Events
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
      { name: 'destination', type: 'address', indexed: false },
    ],
  },
  {
    name: 'ProtectionTriggered',
    type: 'event',
    inputs: [
      { name: 'user', type: 'address', indexed: true },
      { name: 'protocolId', type: 'bytes32', indexed: true },
      { name: 'riskScore', type: 'uint64', indexed: false },
      { name: 'token', type: 'address', indexed: false },
      { name: 'amount', type: 'uint256', indexed: false },
      { name: 'safeAddress', type: 'address', indexed: false },
    ],
  },
  {
    name: 'RuleAdded',
    type: 'event',
    inputs: [
      { name: 'user', type: 'address', indexed: true },
      { name: 'protocolId', type: 'bytes32', indexed: true },
      { name: 'threshold', type: 'uint64', indexed: false },
      { name: 'token', type: 'address', indexed: false },
      { name: 'safeAddress', type: 'address', indexed: false },
    ],
  },
] as const

// ═══════════════════════════════════════════════════════════════════════════
//                              ERC20 ABI
// ═══════════════════════════════════════════════════════════════════════════

export const ERC20_ABI = [
  {
    name: 'approve',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'spender', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ name: '', type: 'bool' }],
  },
  {
    name: 'allowance',
    type: 'function',
    stateMutability: 'view',
    inputs: [
      { name: 'owner', type: 'address' },
      { name: 'spender', type: 'address' },
    ],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'balanceOf',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'account', type: 'address' }],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'decimals',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'uint8' }],
  },
  {
    name: 'symbol',
    type: 'function',
    stateMutability: 'view',
    inputs: [],
    outputs: [{ name: '', type: 'string' }],
  },
] as const

// ═══════════════════════════════════════════════════════════════════════════
//                             TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface ProtectionRule {
  protocolId: `0x${string}`
  token: `0x${string}`
  riskThreshold: bigint
  flags: number
  safeAddress: `0x${string}`
  createdAt: bigint
}

export interface RiskScore {
  score: bigint
  lastUpdated: bigint
  isStale: boolean
}
