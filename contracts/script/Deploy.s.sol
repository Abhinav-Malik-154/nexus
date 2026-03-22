// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/NexusRiskOracle.sol";
import "../src/ProtectionVault.sol";

contract DeployNexus is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        
        vm.startBroadcast(deployerKey);
        
        // Deploy Oracle first
        NexusRiskOracle oracle = new NexusRiskOracle();
        console.log("NexusRiskOracle:", address(oracle));
        
        // Deploy Vault with oracle address
        ProtectionVault vault = new ProtectionVault(
            address(oracle)
        );
        console.log("ProtectionVault:", address(vault));
        
        vm.stopBroadcast();
    }
}