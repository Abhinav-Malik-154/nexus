// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {NexusRiskOracle} from "../src/NexusRiskOracle.sol";
import {ProtectionVault} from "../src/ProtectionVault.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @dev Minimal mock ERC20
contract MockERC20 is ERC20 {
    uint8 private _dec;

    constructor(string memory name, string memory symbol, uint8 dec) ERC20(name, symbol) {
        _dec = dec;
        _mint(msg.sender, 1_000_000 * 10**dec);
    }

    function mint(address to, uint256 amt) external { _mint(to, amt); }
    function decimals() public view override returns (uint8) { return _dec; }
}

/**
 * @title NexusOracleTest
 * @notice Unit tests for NexusRiskOracle
 */
contract NexusOracleTest is Test {
    NexusRiskOracle oracle;

    bytes32 constant AAVE = keccak256("Aave V3");
    bytes32 constant UNI = keccak256("Uniswap");
    bytes32 constant MORPHO = keccak256("Morpho");

    address attacker = makeAddr("attacker");

    function setUp() public {
        oracle = new NexusRiskOracle();
    }

    /*//////////////////////////////////////////////////////////////
                           BASIC OPERATIONS
    //////////////////////////////////////////////////////////////*/

    function test_UpdateRiskScore() public {
        oracle.updateRiskScore(AAVE, 45);
        (uint64 s,,) = oracle.getRiskScore(AAVE);
        assertEq(s, 45);
    }

    function test_UpdateRiskScoreByName() public {
        oracle.updateRiskScoreByName("Aave V3", 45);
        (uint64 s,,) = oracle.getRiskScoreByName("Aave V3");
        assertEq(s, 45);
        assertEq(oracle.protocolNames(AAVE), "Aave V3");
    }

    function test_BatchUpdate() public {
        bytes32[] memory ids = new bytes32[](3);
        uint64[] memory scores = new uint64[](3);
        ids[0] = AAVE;      scores[0] = 30;
        ids[1] = UNI;       scores[1] = 15;
        ids[2] = MORPHO;    scores[2] = 58;

        oracle.batchUpdateRiskScores(ids, scores);

        (uint64 a,,) = oracle.getRiskScore(AAVE);
        (uint64 u,,) = oracle.getRiskScore(UNI);
        (uint64 m,,) = oracle.getRiskScore(MORPHO);

        assertEq(a, 30);
        assertEq(u, 15);
        assertEq(m, 58);
    }

    function test_BatchUpdateByName() public {
        string[] memory names = new string[](2);
        uint64[] memory scores = new uint64[](2);
        names[0] = "Compound V3"; scores[0] = 25;
        names[1] = "Maker";       scores[1] = 40;

        oracle.batchUpdateRiskScoresByName(names, scores);

        (uint64 c,,) = oracle.getRiskScoreByName("Compound V3");
        (uint64 m,,) = oracle.getRiskScoreByName("Maker");

        assertEq(c, 25);
        assertEq(m, 40);
    }

    /*//////////////////////////////////////////////////////////////
                               ALERTS
    //////////////////////////////////////////////////////////////*/

    function test_HighRiskAlert() public {
        vm.expectEmit(true, false, false, true);
        emit NexusRiskOracle.HighRiskAlert(AAVE, 75, uint64(block.timestamp));
        oracle.updateRiskScore(AAVE, 75);
    }

    function test_GetHighRiskProtocols() public {
        oracle.updateRiskScore(AAVE, 30);
        oracle.updateRiskScore(UNI, 75);
        oracle.updateRiskScore(MORPHO, 90);

        bytes32[] memory high = oracle.getHighRiskProtocols();
        assertEq(high.length, 2);
    }

    function test_IsAnyProtocolHighRisk() public {
        oracle.updateRiskScore(AAVE, 30);
        assertFalse(oracle.isAnyProtocolHighRisk());

        oracle.updateRiskScore(UNI, 75);
        assertTrue(oracle.isAnyProtocolHighRisk());
    }

    /*//////////////////////////////////////////////////////////////
                             VALIDATION
    //////////////////////////////////////////////////////////////*/

    function test_RevertOnInvalidScore() public {
        vm.expectRevert(NexusRiskOracle.InvalidScore.selector);
        oracle.updateRiskScore(AAVE, 101);
    }

    function test_RevertOnUnauthorized() public {
        vm.prank(attacker);
        vm.expectRevert(NexusRiskOracle.Unauthorized.selector);
        oracle.updateRiskScore(AAVE, 50);
    }

    function test_RevertOnLengthMismatch() public {
        bytes32[] memory ids = new bytes32[](2);
        uint64[] memory scores = new uint64[](1);

        vm.expectRevert(NexusRiskOracle.ArrayLengthMismatch.selector);
        oracle.batchUpdateRiskScores(ids, scores);
    }

    function test_RevertOnEmptyArray() public {
        bytes32[] memory ids = new bytes32[](0);
        uint64[] memory scores = new uint64[](0);

        vm.expectRevert(NexusRiskOracle.EmptyArray.selector);
        oracle.batchUpdateRiskScores(ids, scores);
    }

    /*//////////////////////////////////////////////////////////////
                              STALENESS
    //////////////////////////////////////////////////////////////*/

    function test_StalenessAfterOneHour() public {
        oracle.updateRiskScore(AAVE, 50);

        (,, bool stale) = oracle.getRiskScore(AAVE);
        assertFalse(stale);

        vm.warp(block.timestamp + 1 hours + 1);
        (,, stale) = oracle.getRiskScore(AAVE);
        assertTrue(stale);
    }

    /*//////////////////////////////////////////////////////////////
                               ADMIN
    //////////////////////////////////////////////////////////////*/

    function test_SetAlertThreshold() public {
        oracle.setAlertThreshold(80);
        assertEq(oracle.alertThreshold(), 80);
    }

    function test_AddAuthorizedUpdater() public {
        address updater = makeAddr("updater");
        oracle.addAuthorizedUpdater(updater);

        vm.prank(updater);
        oracle.updateRiskScore(AAVE, 50);

        (uint64 s,,) = oracle.getRiskScore(AAVE);
        assertEq(s, 50);
    }

    function test_ToProtocolId() public view {
        assertEq(oracle.toProtocolId("Aave V3"), AAVE);
    }

    function test_ProtocolCount() public {
        assertEq(oracle.getProtocolCount(), 0);
        oracle.updateRiskScore(AAVE, 30);
        oracle.updateRiskScore(UNI, 40);
        assertEq(oracle.getProtocolCount(), 2);
    }

    function test_IsTracked() public {
        assertFalse(oracle.isTracked(AAVE));
        oracle.updateRiskScore(AAVE, 30);
        assertTrue(oracle.isTracked(AAVE));
    }
}

/**
 * @title NexusVaultTest
 * @notice Unit tests for ProtectionVault
 */
contract NexusVaultTest is Test {
    NexusRiskOracle oracle;
    ProtectionVault vault;
    MockERC20 usdc;
    MockERC20 weth;

    bytes32 constant AAVE = keccak256("Aave V3");

    address user = makeAddr("user");
    address safe = makeAddr("safe");

    function setUp() public {
        oracle = new NexusRiskOracle();
        vault = new ProtectionVault(address(oracle));
        usdc = new MockERC20("USDC", "USDC", 6);
        weth = new MockERC20("WETH", "WETH", 18);

        usdc.mint(user, 100_000e6);
        weth.mint(user, 100e18);
    }

    /*//////////////////////////////////////////////////////////////
                              DEPOSITS
    //////////////////////////////////////////////////////////////*/

    function test_Deposit() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vm.stopPrank();

        assertEq(vault.getBalance(user, address(usdc)), amt);
        assertTrue(vault.hasVault(user));
    }

    function test_RevertOnZeroDeposit() public {
        vm.prank(user);
        vm.expectRevert(ProtectionVault.ZeroAmount.selector);
        vault.deposit(address(usdc), 0);
    }

    /*//////////////////////////////////////////////////////////////
                          PROTECTION RULES
    //////////////////////////////////////////////////////////////*/

    function test_AddProtectionRule() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        ProtectionVault.ProtectionRule[] memory rules = vault.getRules(user);
        assertEq(rules.length, 1);
        assertEq(rules[0].riskThreshold, 70);
        assertEq(rules[0].flags & 1, 1);
    }

    function test_AddProtectionRuleByName() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRuleByName("Aave V3", 70, address(usdc), safe);
        vm.stopPrank();

        assertEq(vault.getRuleCount(user), 1);
    }

    function test_RevertOnRuleWithoutVault() public {
        vm.prank(user);
        vm.expectRevert(ProtectionVault.NoVault.selector);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
    }

    function test_RevertOnInvalidThreshold() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);

        vm.expectRevert(ProtectionVault.InvalidThreshold.selector);
        vault.addProtectionRule(AAVE, 101, address(usdc), safe);
        vm.stopPrank();
    }

    function test_RevertOnInvalidSafeAddress() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);

        vm.expectRevert(ProtectionVault.ZeroAddress.selector);
        vault.addProtectionRule(AAVE, 70, address(usdc), address(0));
        vm.stopPrank();
    }

    /*//////////////////////////////////////////////////////////////
                         PROTECTION LOGIC
    //////////////////////////////////////////////////////////////*/

    function test_ProtectionTriggersOnHighRisk() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        oracle.updateRiskScore(AAVE, 75);

        uint256 safeBefore = usdc.balanceOf(safe);
        vault.checkAndProtect(user);

        assertEq(usdc.balanceOf(safe) - safeBefore, amt);
        assertEq(vault.getBalance(user, address(usdc)), 0);
    }

    function test_NoProtectionBelowThreshold() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        oracle.updateRiskScore(AAVE, 50);
        vault.checkAndProtect(user);

        assertEq(vault.getBalance(user, address(usdc)), amt);
    }

    function test_NoProtectionOnStaleData() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        oracle.updateRiskScore(AAVE, 80);
        vm.warp(block.timestamp + 1 hours + 1);
        vault.checkAndProtect(user);

        assertEq(vault.getBalance(user, address(usdc)), amt);
    }

    /*//////////////////////////////////////////////////////////////
                            WITHDRAWALS
    //////////////////////////////////////////////////////////////*/

    function test_Withdraw() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);

        uint256 before = usdc.balanceOf(user);
        vault.withdraw(address(usdc), amt);
        vm.stopPrank();

        assertEq(usdc.balanceOf(user) - before, amt);
        assertEq(vault.getBalance(user, address(usdc)), 0);
    }

    function test_RevertOnInsufficientBalance() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);

        vm.expectRevert(ProtectionVault.InsufficientBalance.selector);
        vault.withdraw(address(usdc), amt + 1);
        vm.stopPrank();
    }

    /*//////////////////////////////////////////////////////////////
                        CHAINLINK AUTOMATION
    //////////////////////////////////////////////////////////////*/

    function test_CheckUpkeep() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        (bool needed,) = vault.checkUpkeep("");
        assertFalse(needed);

        oracle.updateRiskScore(AAVE, 75);
        (needed,) = vault.checkUpkeep("");
        assertTrue(needed);
    }

    function test_PerformUpkeep() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        oracle.updateRiskScore(AAVE, 75);

        (bool needed, bytes memory data) = vault.checkUpkeep("");
        assertTrue(needed);

        vault.performUpkeep(data);

        assertEq(vault.getBalance(user, address(usdc)), 0);
        assertEq(usdc.balanceOf(safe), amt);
    }

    function test_BatchCheckAndProtect() public {
        address user2 = makeAddr("user2");
        uint256 amt = 1000e6;
        usdc.mint(user2, amt);

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vm.stopPrank();

        vm.startPrank(user2);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 60, address(usdc), user2);
        vm.stopPrank();

        oracle.updateRiskScore(AAVE, 75);

        address[] memory users = new address[](2);
        users[0] = user;
        users[1] = user2;
        vault.batchCheckAndProtect(users);

        assertEq(vault.getBalance(user, address(usdc)), 0);
        assertEq(vault.getBalance(user2, address(usdc)), 0);
    }

    function test_DeactivateRule() public {
        uint256 amt = 1000e6;

        vm.startPrank(user);
        usdc.approve(address(vault), amt);
        vault.deposit(address(usdc), amt);
        vault.addProtectionRule(AAVE, 70, address(usdc), safe);
        vault.deactivateRule(0);
        vm.stopPrank();

        ProtectionVault.ProtectionRule[] memory rules = vault.getRules(user);
        assertEq(rules[0].flags & 1, 0);

        oracle.updateRiskScore(AAVE, 90);
        vault.checkAndProtect(user);
        assertEq(vault.getBalance(user, address(usdc)), amt); // Not triggered
    }
}
