// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {NexusRiskOracle} from "../src/NexusRiskOracle.sol";
import {ProtectionVault} from "../src/ProtectionVault.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title DeployNexus
 * @notice Production deployment script for Nexus Protocol
 *
 * @dev Usage:
 *   forge script script/Deploy.s.sol:DeployNexus \
 *     --rpc-url $RPC_URL \
 *     --broadcast \
 *     --verify \
 *     --etherscan-api-key $API_KEY
 */
contract DeployNexus is Script {
    // Top DeFi protocols by TVL
    string[10] internal _protocols = [
        "Lido", "Aave V3", "EigenLayer", "ether.fi", "Ethena",
        "Uniswap V3", "Maker", "Pendle", "Compound V3", "Morpho"
    ];

    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);

        console.log("");
        console.log("================================================");
        console.log("        NEXUS PROTOCOL DEPLOYMENT");
        console.log("================================================");
        console.log("");
        console.log("  Deployer:  ", deployer);
        console.log("  Chain ID:  ", block.chainid);
        console.log("  Timestamp: ", block.timestamp);
        console.log("");

        vm.startBroadcast(pk);

        // 1. Deploy Oracle
        NexusRiskOracle oracle = new NexusRiskOracle();
        console.log("[1/3] NexusRiskOracle:", address(oracle));

        // 2. Deploy Vault
        ProtectionVault vault = new ProtectionVault(address(oracle));
        console.log("[2/3] ProtectionVault:", address(vault));

        // 3. Seed protocols
        string[] memory names = new string[](10);
        uint64[] memory scores = new uint64[](10);
        for (uint256 i; i < 10; ++i) {
            names[i] = _protocols[i];
            scores[i] = 0; // Start healthy
        }
        oracle.batchUpdateRiskScoresByName(names, scores);
        console.log("[3/3] Seeded", names.length, "protocols");

        vm.stopBroadcast();

        console.log("");
        console.log("================================================");
        console.log("        DEPLOYMENT COMPLETE");
        console.log("================================================");
        console.log("");
        console.log("  NexusRiskOracle:", address(oracle));
        console.log("  ProtectionVault:", address(vault));
        console.log("");
        console.log("  Next steps:");
        console.log("  1. Verify contracts on explorer");
        console.log("  2. Add backend wallet as updater");
        console.log("  3. Register vault with Chainlink Automation");
        console.log("  4. Update frontend contract addresses");
        console.log("");
    }
}

/**
 * @title DeployMockToken
 * @notice Deploy mock USDC for testnet testing
 */
contract DeployMockToken is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);

        MockUSDC usdc = new MockUSDC();
        console.log("MockUSDC:", address(usdc));

        vm.stopBroadcast();
    }
}

/// @dev Simple mock USDC for testing
contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USDC", "USDC") {
        _mint(msg.sender, 1_000_000e6);
    }

    function mint(address to, uint256 amt) external {
        _mint(to, amt);
    }

    function decimals() public pure override returns (uint8) { return 6; }
}

/**
 * @title AddUpdater
 * @notice Add authorized updater to oracle
 */
contract AddUpdater is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address oracle = vm.envAddress("ORACLE_ADDRESS");
        address updater = vm.envAddress("UPDATER_ADDRESS");

        vm.startBroadcast(pk);
        NexusRiskOracle(oracle).addAuthorizedUpdater(updater);
        console.log("Added updater:", updater);
        vm.stopBroadcast();
    }
}
