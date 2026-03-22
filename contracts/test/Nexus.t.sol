// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/NexusRiskOracle.sol";
import "../src/ProtectionVault.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USDC", "USDC") {
        _mint(msg.sender, 1_000_000 * 10**18);
    }
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract NexusTest is Test {
    NexusRiskOracle public oracle;
    ProtectionVault public vault;
    MockUSDC public usdc;

    address public user = address(0x1234);
    address public safeAddress = address(0x5678);

    function setUp() public {
        oracle = new NexusRiskOracle();
        vault = new ProtectionVault(address(oracle));
        usdc = new MockUSDC();
        usdc.mint(user, 10_000 * 10**18);
    }

    function test_UpdateRiskScore() public {
        oracle.updateRiskScore("Aave V3", 45);
        (uint256 score,,) = oracle.getRiskScore("Aave V3");
        assertEq(score, 45);
    }

    function test_BatchUpdateRiskScores() public {
        string[] memory protocols = new string[](3);
        uint256[] memory scores = new uint256[](3);
        protocols[0] = "Aave V3";
        protocols[1] = "Uniswap";
        protocols[2] = "Morpho V1";
        scores[0] = 30;
        scores[1] = 15;
        scores[2] = 58;
        oracle.batchUpdateRiskScores(protocols, scores);
        (uint256 aaveScore,,) = oracle.getRiskScore("Aave V3");
        (uint256 uniScore,,) = oracle.getRiskScore("Uniswap");
        (uint256 morphoScore,,) = oracle.getRiskScore("Morpho V1");
        assertEq(aaveScore, 30);
        assertEq(uniScore, 15);
        assertEq(morphoScore, 58);
    }

    function test_HighRiskAlert() public {
        vm.expectEmit(true, false, false, true);
        emit NexusRiskOracle.HighRiskAlert("OKX", 75, block.timestamp);
        oracle.updateRiskScore("OKX", 75);
    }

    function test_GetHighRiskProtocols() public {
        oracle.updateRiskScore("Aave V3", 30);
        oracle.updateRiskScore("OKX", 75);
        oracle.updateRiskScore("Morpho V1", 58);
        oracle.updateRiskScore("BadProtocol", 90);
        string[] memory highRisk = oracle.getHighRiskProtocols();
        assertEq(highRisk.length, 2);
    }

    function test_RevertOnInvalidScore() public {
        vm.expectRevert("Score must be 0-100");
        oracle.updateRiskScore("Aave V3", 101);
    }

    function test_UnauthorizedUpdater() public {
        vm.prank(address(0xdead));
        vm.expectRevert("Not authorized to update scores");
        oracle.updateRiskScore("Aave V3", 50);
    }

    function test_DepositTokens() public {
        uint256 amount = 1000 * 10**18;
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(address(usdc), amount);
        vm.stopPrank();
        uint256 balance = vault.getBalance(user, address(usdc));
        assertEq(balance, amount);
    }

    function test_AddProtectionRule() public {
        uint256 amount = 1000 * 10**18;
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(address(usdc), amount);
        vault.addProtectionRule("Aave V3", 70, address(usdc), safeAddress);
        vm.stopPrank();
        ProtectionVault.ProtectionRule[] memory rules = vault.getRules(user);
        assertEq(rules.length, 1);
        assertEq(rules[0].riskThreshold, 70);
        assertTrue(rules[0].isActive);
    }

    function test_ProtectionTriggersOnHighRisk() public {
        uint256 amount = 1000 * 10**18;
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(address(usdc), amount);
        vault.addProtectionRule("Aave V3", 70, address(usdc), safeAddress);
        vm.stopPrank();
        oracle.updateRiskScore("Aave V3", 75);
        uint256 safeBefore = usdc.balanceOf(safeAddress);
        vault.checkAndProtect(user);
        uint256 safeAfter = usdc.balanceOf(safeAddress);
        assertEq(safeAfter - safeBefore, amount);
        assertEq(vault.getBalance(user, address(usdc)), 0);
    }

    function test_NoProtectionBelowThreshold() public {
        uint256 amount = 1000 * 10**18;
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(address(usdc), amount);
        vault.addProtectionRule("Aave V3", 70, address(usdc), safeAddress);
        vm.stopPrank();
        oracle.updateRiskScore("Aave V3", 50);
        vault.checkAndProtect(user);
        assertEq(vault.getBalance(user, address(usdc)), amount);
    }

    function test_ManualWithdraw() public {
        uint256 amount = 1000 * 10**18;
        vm.startPrank(user);
        usdc.approve(address(vault), amount);
        vault.deposit(address(usdc), amount);
        uint256 userBefore = usdc.balanceOf(user);
        vault.withdraw(address(usdc), amount);
        uint256 userAfter = usdc.balanceOf(user);
        vm.stopPrank();
        assertEq(userAfter - userBefore, amount);
    }
}