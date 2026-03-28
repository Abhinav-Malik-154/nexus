// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {NexusRiskOracleV2} from "../src/NexusRiskOracleV2.sol";
import {ProtectionVaultV2} from "../src/ProtectionVaultV2.sol";

/**
 * @title DeployV2
 * @notice Production deployment script for Nexus V2 contracts
 *
 * Usage:
 *   forge script script/DeployV2.s.sol --rpc-url $RPC_URL --broadcast --verify
 *
 * With Ledger:
 *   forge script script/DeployV2.s.sol --rpc-url $RPC_URL --broadcast --verify --ledger
 */
contract DeployV2 is Script {
    function run() external {
        // Load deployer from environment
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);

        console2.log("Deployer:", deployer);
        console2.log("Chain ID:", block.chainid);
        console2.log("");

        vm.startBroadcast(deployerKey);

        // 1. Deploy Oracle implementation
        NexusRiskOracleV2 oracleImpl = new NexusRiskOracleV2();
        console2.log("Oracle Implementation:", address(oracleImpl));

        // 2. Deploy Oracle proxy
        bytes memory oracleData = abi.encodeCall(NexusRiskOracleV2.initialize, (deployer));
        ERC1967Proxy oracleProxy = new ERC1967Proxy(address(oracleImpl), oracleData);
        NexusRiskOracleV2 oracle = NexusRiskOracleV2(address(oracleProxy));
        console2.log("Oracle Proxy:", address(oracle));

        // 3. Deploy Vault implementation
        ProtectionVaultV2 vaultImpl = new ProtectionVaultV2();
        console2.log("Vault Implementation:", address(vaultImpl));

        // 4. Deploy Vault proxy
        bytes memory vaultData = abi.encodeCall(ProtectionVaultV2.initialize, (address(oracle), deployer));
        ERC1967Proxy vaultProxy = new ERC1967Proxy(address(vaultImpl), vaultData);
        ProtectionVaultV2 vault = ProtectionVaultV2(address(vaultProxy));
        console2.log("Vault Proxy:", address(vault));

        vm.stopBroadcast();

        // Summary
        console2.log("");
        console2.log("=== DEPLOYMENT COMPLETE ===");
        console2.log("");
        console2.log("Oracle (proxy):", address(oracle));
        console2.log("Oracle (impl):", address(oracleImpl));
        console2.log("Vault (proxy):", address(vault));
        console2.log("Vault (impl):", address(vaultImpl));
        console2.log("");
        console2.log("Admin:", deployer);
        console2.log("Alert Threshold:", oracle.alertThreshold());
        console2.log("Batch Size:", vault.batchSize());
    }
}

/**
 * @title UpgradeOracle
 * @notice Upgrade Oracle to new implementation
 */
contract UpgradeOracle is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address oracleProxy = vm.envAddress("ORACLE_PROXY");

        vm.startBroadcast(deployerKey);

        // Deploy new implementation
        NexusRiskOracleV2 newImpl = new NexusRiskOracleV2();
        console2.log("New Oracle Implementation:", address(newImpl));

        // Upgrade proxy
        NexusRiskOracleV2(oracleProxy).upgradeToAndCall(address(newImpl), "");
        console2.log("Oracle upgraded successfully");

        vm.stopBroadcast();
    }
}

/**
 * @title UpgradeVault
 * @notice Upgrade Vault to new implementation
 */
contract UpgradeVault is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address vaultProxy = vm.envAddress("VAULT_PROXY");

        vm.startBroadcast(deployerKey);

        // Deploy new implementation
        ProtectionVaultV2 newImpl = new ProtectionVaultV2();
        console2.log("New Vault Implementation:", address(newImpl));

        // Upgrade proxy
        ProtectionVaultV2(vaultProxy).upgradeToAndCall(address(newImpl), "");
        console2.log("Vault upgraded successfully");

        vm.stopBroadcast();
    }
}
