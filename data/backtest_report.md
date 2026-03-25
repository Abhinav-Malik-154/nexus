# Nexus GNN Backtest Report

**Generated:** 2026-03-26 00:50:29

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Exploits Tested | 21 |
| Protocols in Model | 6 |
| Exploits Detected | 0 |
| **Detection Rate** | **0.0%** |
| **Loss Coverage** | **0.0%** |
| Avg Risk Score (exploited) | 23.0/100 |

## Detailed Results

| Protocol | Date | Loss | Risk Score | Flagged? | Type |
|----------|------|------|------------|----------|------|
| Terra Luna | 2022-05-09 | $40.00B | 25 | ❌ | algorithmic_stablecoin_death_spiral |
| FTX | 2022-11-11 | $8.00B | 25 | ❌ | fraud_insolvency |
| Celsius | 2022-06-13 | $4.70B | 25 | ❌ | insolvency |
| Ronin Bridge | 2022-03-29 | $624M | N/A | ❌ | bridge_exploit |
| Poly Network | 2021-08-10 | $611M | N/A | ❌ | bridge_exploit |
| BNB Bridge | 2022-10-06 | $586M | N/A | ❌ | bridge_exploit |
| Wormhole | 2022-02-02 | $320M | N/A | ❌ | bridge_exploit |
| PlayDapp | 2024-02-09 | $290M | N/A | ❌ | private_key_compromise |
| Euler Finance | 2023-03-13 | $197M | 26 | ❌ | flash_loan_attack |
| Nomad Bridge | 2022-08-01 | $190M | N/A | ❌ | bridge_exploit |
| Beanstalk | 2022-04-17 | $182M | N/A | ❌ | governance_attack |
| Cream Finance | 2021-10-27 | $130M | 25 | ❌ | flash_loan_attack |
| BonqDAO | 2023-02-03 | $120M | N/A | ❌ | oracle_manipulation |
| BadgerDAO | 2021-12-02 | $120M | N/A | ❌ | frontend_attack |
| Mango Markets | 2022-10-11 | $114M | N/A | ❌ | oracle_manipulation |
| Atomic Wallet | 2023-06-03 | $100M | N/A | ❌ | wallet_exploit |
| Harmony Horizon | 2022-06-24 | $100M | N/A | ❌ | bridge_exploit |
| Qubit Finance | 2022-01-28 | $80M | N/A | ❌ | smart_contract_exploit |
| CoinEx | 2023-09-12 | $70M | N/A | ❌ | hot_wallet_compromise |
| Curve Finance | 2023-07-30 | $62M | 14 | ❌ | smart_contract_exploit |
| KyberSwap | 2023-11-22 | $55M | N/A | ❌ | smart_contract_exploit |

## Detection by Exploit Type

| Type | Total | Flagged | Rate |
|------|-------|---------|------|
| bridge_exploit | 6 | 0 | 0% |
| smart_contract_exploit | 3 | 0 | 0% |
| flash_loan_attack | 2 | 0 | 0% |
| oracle_manipulation | 2 | 0 | 0% |
| private_key_compromise | 1 | 0 | 0% |
| hot_wallet_compromise | 1 | 0 | 0% |
| wallet_exploit | 1 | 0 | 0% |
| fraud_insolvency | 1 | 0 | 0% |
| insolvency | 1 | 0 | 0% |
| algorithmic_stablecoin_death_spiral | 1 | 0 | 0% |
| governance_attack | 1 | 0 | 0% |
| frontend_attack | 1 | 0 | 0% |

## Key Findings

### Missed Exploits (False Negatives)

- **PlayDapp** (2024-02-09): Risk score only 0/100
- **KyberSwap** (2023-11-22): Risk score only 0/100
- **CoinEx** (2023-09-12): Risk score only 0/100
- **Curve Finance** (2023-07-30): Risk score only 14/100
- **Atomic Wallet** (2023-06-03): Risk score only 0/100

## Recommendations

- ⚠️ Detection rate below 50% - consider retraining with more features
- ⚠️ Contagion detection low - improve graph connectivity
- ⚠️ Poor detection for 'smart_contract_exploit' exploits (0%)
- ⚠️ Poor detection for 'flash_loan_attack' exploits (0%)
- ⚠️ Poor detection for 'oracle_manipulation' exploits (0%)
- ⚠️ Poor detection for 'bridge_exploit' exploits (0%)
