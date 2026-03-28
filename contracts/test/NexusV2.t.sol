// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {NexusRiskOracleV2} from "../src/NexusRiskOracleV2.sol";
import {ProtectionVaultV2} from "../src/ProtectionVaultV2.sol";

/// @dev Mock ERC20 for testing
contract MockToken is ERC20 {
    constructor() ERC20("Mock", "MCK") {}
    function mint(address to, uint256 amt) external { _mint(to, amt); }
}

/**
 * @title NexusV2Test
 * @notice Comprehensive test suite for production-grade V2 contracts
 */
contract NexusV2Test is Test {
    NexusRiskOracleV2 oracle;
    NexusRiskOracleV2 oracleImpl;
    ProtectionVaultV2 vault;
    ProtectionVaultV2 vaultImpl;
    MockToken token;

    address admin = makeAddr("admin");
    address updater = makeAddr("updater");
    address keeper = makeAddr("keeper");
    address user1 = makeAddr("user1");
    address user2 = makeAddr("user2");
    address safe = makeAddr("safe");

    bytes32 constant PROTOCOL_A = keccak256("protocol-a");
    bytes32 constant PROTOCOL_B = keccak256("protocol-b");

    function setUp() public {
        // Deploy implementations
        oracleImpl = new NexusRiskOracleV2();
        vaultImpl = new ProtectionVaultV2();

        // Deploy proxies
        bytes memory oracleData = abi.encodeCall(NexusRiskOracleV2.initialize, (admin));
        ERC1967Proxy oracleProxy = new ERC1967Proxy(address(oracleImpl), oracleData);
        oracle = NexusRiskOracleV2(address(oracleProxy));

        bytes memory vaultData = abi.encodeCall(ProtectionVaultV2.initialize, (address(oracle), admin));
        ERC1967Proxy vaultProxy = new ERC1967Proxy(address(vaultImpl), vaultData);
        vault = ProtectionVaultV2(address(vaultProxy));

        // Setup roles
        vm.startPrank(admin);
        oracle.grantRole(oracle.UPDATER_ROLE(), updater);
        vault.grantRole(vault.KEEPER_ROLE(), keeper);
        vm.stopPrank();

        // Deploy token
        token = new MockToken();
    }

    /*//////////////////////////////////////////////////////////////
                          ORACLE BASIC TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Oracle_Initialize() public view {
        assertEq(oracle.alertThreshold(), 70);
        assertTrue(oracle.hasRole(oracle.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.UPDATER_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.UPDATER_ROLE(), updater));
    }

    function test_Oracle_UpdateScore() public {
        skip(5 minutes + 1); // bypass rate limit from initialize
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 50);

        (uint64 score, uint64 ts, bool stale) = oracle.getScore(PROTOCOL_A);
        assertEq(score, 50);
        assertEq(ts, block.timestamp);
        assertFalse(stale);
        assertTrue(oracle.isTracked(PROTOCOL_A));
    }

    function test_Oracle_UpdateScoreByName() public {
        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScoreByName("aave-v3", 45);

        bytes32 id = oracle.toId("aave-v3");
        (uint64 score,,) = oracle.getScore(id);
        assertEq(score, 45);
        assertEq(oracle.names(id), "aave-v3");
    }

    function test_Oracle_BatchUpdate() public {
        skip(5 minutes + 1);
        bytes32[] memory ids = new bytes32[](3);
        ids[0] = PROTOCOL_A;
        ids[1] = PROTOCOL_B;
        ids[2] = keccak256("protocol-c");

        uint64[] memory scores = new uint64[](3);
        scores[0] = 30;
        scores[1] = 60;
        scores[2] = 90;

        vm.prank(updater);
        oracle.batchUpdate(ids, scores);

        (uint64 s1,,) = oracle.getScore(ids[0]);
        (uint64 s2,,) = oracle.getScore(ids[1]);
        (uint64 s3,,) = oracle.getScore(ids[2]);

        assertEq(s1, 30);
        assertEq(s2, 60);
        assertEq(s3, 90);
        assertEq(oracle.protocolCount(), 3);
    }

    function test_Oracle_InvalidScoreReverts() public {
        skip(5 minutes + 1);
        vm.prank(updater);
        vm.expectRevert(NexusRiskOracleV2.InvalidScore.selector);
        oracle.updateScore(PROTOCOL_A, 101);
    }

    function test_Oracle_UnauthorizedReverts() public {
        vm.prank(user1);
        vm.expectRevert();
        oracle.updateScore(PROTOCOL_A, 50);
    }

    /*//////////////////////////////////////////////////////////////
                         ORACLE RATE LIMITING
    //////////////////////////////////////////////////////////////*/

    function test_Oracle_RateLimiting() public {
        skip(5 minutes + 1);
        vm.startPrank(updater);
        oracle.updateScore(PROTOCOL_A, 50);

        // Immediate second call should fail
        vm.expectRevert(NexusRiskOracleV2.RateLimited.selector);
        oracle.updateScore(PROTOCOL_A, 60);

        // After 5 minutes, should work
        skip(5 minutes + 1);
        oracle.updateScore(PROTOCOL_A, 60);
        vm.stopPrank();

        (uint64 score,,) = oracle.getScore(PROTOCOL_A);
        assertEq(score, 60);
    }

    /*//////////////////////////////////////////////////////////////
                          ORACLE TIMELOCK
    //////////////////////////////////////////////////////////////*/

    function test_Oracle_ThresholdTimelock() public {
        vm.startPrank(admin);

        // Queue threshold change
        oracle.queueThreshold(80);
        (uint64 pending, uint64 executeAfter) = oracle.pendingThreshold();
        assertEq(pending, 80);
        assertEq(executeAfter, block.timestamp + 24 hours);

        // Cannot execute immediately
        vm.expectRevert(NexusRiskOracleV2.TimelockNotReady.selector);
        oracle.executeThreshold();

        // Wait for timelock
        skip(24 hours + 1);
        oracle.executeThreshold();

        assertEq(oracle.alertThreshold(), 80);
        vm.stopPrank();
    }

    function test_Oracle_CancelThreshold() public {
        vm.startPrank(admin);
        oracle.queueThreshold(80);
        oracle.cancelThreshold();

        (uint64 pending,) = oracle.pendingThreshold();
        assertEq(pending, 0);
        assertEq(oracle.alertThreshold(), 70); // unchanged
        vm.stopPrank();
    }

    /*//////////////////////////////////////////////////////////////
                         ORACLE PAGINATION
    //////////////////////////////////////////////////////////////*/

    function test_Oracle_PaginatedProtocols() public {
        // Create 25 protocols
        vm.startPrank(updater);
        for (uint256 i = 0; i < 25; i++) {
            skip(5 minutes + 1); // Bypass rate limit first
            bytes32 id = keccak256(abi.encodePacked("proto-", i));
            oracle.updateScore(id, uint64(i * 4));
        }
        vm.stopPrank();

        // Get first page
        (bytes32[] memory page1, uint256 total) = oracle.getProtocols(0, 10);
        assertEq(page1.length, 10);
        assertEq(total, 25);

        // Get second page
        (bytes32[] memory page2,) = oracle.getProtocols(10, 10);
        assertEq(page2.length, 10);

        // Get last page
        (bytes32[] memory page3,) = oracle.getProtocols(20, 10);
        assertEq(page3.length, 5);
    }

    function test_Oracle_HighRiskPaginated() public {
        vm.startPrank(updater);
        // Create mix of high/low risk
        for (uint256 i = 0; i < 10; i++) {
            skip(5 minutes + 1);
            bytes32 id = keccak256(abi.encodePacked("p-", i));
            uint64 score = i % 2 == 0 ? 80 : 30; // alternating
            oracle.updateScore(id, score);
        }
        vm.stopPrank();

        (bytes32[] memory high, uint256 total) = oracle.getHighRisk(0, 100);
        assertEq(total, 5); // 5 high risk (even indices)
        assertEq(high.length, 5);
    }

    /*//////////////////////////////////////////////////////////////
                          ORACLE STALENESS
    //////////////////////////////////////////////////////////////*/

    function test_Oracle_Staleness() public {
        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 50);

        (,, bool stale1) = oracle.getScore(PROTOCOL_A);
        assertFalse(stale1);

        skip(1 hours + 1);
        (,, bool stale2) = oracle.getScore(PROTOCOL_A);
        assertTrue(stale2);
    }

    /*//////////////////////////////////////////////////////////////
                           ORACLE PAUSE
    //////////////////////////////////////////////////////////////*/

    function test_Oracle_Pause() public {
        skip(5 minutes + 1);
        vm.prank(admin);
        oracle.pause();

        vm.prank(updater);
        vm.expectRevert();
        oracle.updateScore(PROTOCOL_A, 50);

        vm.prank(admin);
        oracle.unpause();

        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 50);
    }

    /*//////////////////////////////////////////////////////////////
                          VAULT BASIC TESTS
    //////////////////////////////////////////////////////////////*/

    function test_Vault_Initialize() public view {
        assertEq(address(vault.oracle()), address(oracle));
        assertEq(vault.batchSize(), 20);
        assertTrue(vault.hasRole(vault.DEFAULT_ADMIN_ROLE(), admin));
    }

    function test_Vault_Deposit() public {
        token.mint(user1, 1000e18);

        vm.startPrank(user1);
        token.approve(address(vault), 1000e18);
        vault.deposit(address(token), 1000e18);
        vm.stopPrank();

        assertEq(vault.getBalance(user1, address(token)), 1000e18);
        assertTrue(vault.hasVault(user1));
        assertEq(vault.totalUsers(), 1);
    }

    function test_Vault_Withdraw() public {
        token.mint(user1, 1000e18);

        vm.startPrank(user1);
        token.approve(address(vault), 1000e18);
        vault.deposit(address(token), 1000e18);
        vault.withdraw(address(token), 400e18);
        vm.stopPrank();

        assertEq(vault.getBalance(user1, address(token)), 600e18);
        assertEq(token.balanceOf(user1), 400e18);
    }

    function test_Vault_EmergencyWithdraw() public {
        token.mint(user1, 1000e18);

        vm.startPrank(user1);
        token.approve(address(vault), 1000e18);
        vault.deposit(address(token), 1000e18);
        vm.stopPrank();

        // Pause vault
        vm.prank(admin);
        vault.pause();

        // Normal withdraw should fail
        vm.prank(user1);
        vm.expectRevert();
        vault.withdraw(address(token), 500e18);

        // Emergency withdraw should work
        vm.prank(user1);
        vault.emergencyWithdraw(address(token));

        assertEq(vault.getBalance(user1, address(token)), 0);
        assertEq(token.balanceOf(user1), 1000e18);
    }

    /*//////////////////////////////////////////////////////////////
                          VAULT RULES
    //////////////////////////////////////////////////////////////*/

    function test_Vault_CreateRule() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.prank(user1);
        uint256 ruleId = vault.createRule(PROTOCOL_A, 70, address(token), safe);

        assertEq(ruleId, 0);
        assertEq(vault.ruleCount(user1), 1);

        ProtectionVaultV2.Rule memory rule = vault.getRule(user1, 0);
        assertEq(rule.protocolId, PROTOCOL_A);
        assertEq(rule.threshold, 70);
        assertEq(rule.token, address(token));
        assertEq(rule.safe, safe);
        assertTrue(rule.active);
    }

    function test_Vault_ToggleRule() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.startPrank(user1);
        vault.createRule(PROTOCOL_A, 70, address(token), safe);

        vault.deactivateRule(0);
        assertFalse(vault.getRule(user1, 0).active);

        vault.activateRule(0);
        assertTrue(vault.getRule(user1, 0).active);
        vm.stopPrank();
    }

    function test_Vault_TooManyRulesReverts() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.startPrank(user1);
        for (uint256 i = 0; i < 20; i++) {
            bytes32 id = keccak256(abi.encodePacked("p-", i));
            vault.createRule(id, 70, address(token), safe);
        }

        vm.expectRevert(ProtectionVaultV2.TooManyRules.selector);
        vault.createRule(keccak256("extra"), 70, address(token), safe);
        vm.stopPrank();
    }

    /*//////////////////////////////////////////////////////////////
                       VAULT PROTECTION
    //////////////////////////////////////////////////////////////*/

    function test_Vault_ProtectionTriggers() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.prank(user1);
        vault.createRule(PROTOCOL_A, 70, address(token), safe);

        // Update oracle to high risk
        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 80);

        // Trigger protection
        vault.protect(user1);

        // Funds should be transferred to safe
        assertEq(vault.getBalance(user1, address(token)), 0);
        assertEq(token.balanceOf(safe), 1000e18);

        // Rule should be deactivated
        assertFalse(vault.getRule(user1, 0).active);
    }

    function test_Vault_ProtectionIgnoresLowRisk() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.prank(user1);
        vault.createRule(PROTOCOL_A, 70, address(token), safe);

        // Update oracle to low risk
        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 50);

        // Protection should not trigger
        vault.protect(user1);

        assertEq(vault.getBalance(user1, address(token)), 1000e18);
        assertEq(token.balanceOf(safe), 0);
    }

    function test_Vault_ProtectionIgnoresStaleData() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.prank(user1);
        vault.createRule(PROTOCOL_A, 70, address(token), safe);

        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 90);

        // Make data stale
        skip(2 hours);

        // Protection should not trigger due to staleness
        vault.protect(user1);

        assertEq(vault.getBalance(user1, address(token)), 1000e18);
    }

    /*//////////////////////////////////////////////////////////////
                      VAULT CHAINLINK AUTOMATION
    //////////////////////////////////////////////////////////////*/

    function test_Vault_CheckUpkeep() public {
        _setupUserWithDeposit(user1, 1000e18);
        _setupUserWithDeposit(user2, 500e18);

        vm.prank(user1);
        vault.createRule(PROTOCOL_A, 70, address(token), safe);
        vm.prank(user2);
        vault.createRule(PROTOCOL_A, 70, address(token), makeAddr("safe2"));

        // No high risk yet
        (bool needed1,) = vault.checkUpkeep("");
        assertFalse(needed1);

        // Set high risk
        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 80);

        // Should need upkeep
        (bool needed2, bytes memory data) = vault.checkUpkeep("");
        assertTrue(needed2);

        // Decode and verify
        address[] memory toProtect = abi.decode(data, (address[]));
        assertEq(toProtect.length, 2);
    }

    function test_Vault_PerformUpkeep() public {
        _setupUserWithDeposit(user1, 1000e18);

        vm.prank(user1);
        vault.createRule(PROTOCOL_A, 70, address(token), safe);

        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, 80);

        (bool needed, bytes memory data) = vault.checkUpkeep("");
        assertTrue(needed);

        // Perform upkeep as keeper
        vm.prank(keeper);
        vault.performUpkeep(data);

        assertEq(vault.getBalance(user1, address(token)), 0);
        assertEq(token.balanceOf(safe), 1000e18);
    }

    /*//////////////////////////////////////////////////////////////
                         VAULT PAGINATION
    //////////////////////////////////////////////////////////////*/

    function test_Vault_PaginatedUsers() public {
        // Create 15 users
        for (uint256 i = 0; i < 15; i++) {
            address u = makeAddr(string.concat("user-", vm.toString(i)));
            token.mint(u, 100e18);
            vm.startPrank(u);
            token.approve(address(vault), 100e18);
            vault.deposit(address(token), 100e18);
            vm.stopPrank();
        }

        (address[] memory page1, uint256 total) = vault.getUsers(0, 10);
        assertEq(page1.length, 10);
        assertEq(total, 15);

        (address[] memory page2,) = vault.getUsers(10, 10);
        assertEq(page2.length, 5);
    }

    /*//////////////////////////////////////////////////////////////
                            VAULT ADMIN
    //////////////////////////////////////////////////////////////*/

    function test_Vault_SetOracle() public {
        NexusRiskOracleV2 newOracle = new NexusRiskOracleV2();

        vm.prank(admin);
        vault.setOracle(address(newOracle));

        assertEq(address(vault.oracle()), address(newOracle));
    }

    function test_Vault_SetBatchSize() public {
        vm.prank(admin);
        vault.setBatchSize(30);

        assertEq(vault.batchSize(), 30);
    }

    /*//////////////////////////////////////////////////////////////
                          FUZZ TESTS
    //////////////////////////////////////////////////////////////*/

    function testFuzz_Oracle_ValidScores(uint64 score) public {
        score = uint64(bound(score, 0, 100));
        skip(5 minutes + 1);

        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, score);

        (uint64 s,,) = oracle.getScore(PROTOCOL_A);
        assertEq(s, score);
    }

    function testFuzz_Oracle_InvalidScoresRevert(uint64 score) public {
        vm.assume(score > 100);
        skip(5 minutes + 1);

        vm.prank(updater);
        vm.expectRevert(NexusRiskOracleV2.InvalidScore.selector);
        oracle.updateScore(PROTOCOL_A, score);
    }

    function testFuzz_Vault_DepositWithdraw(uint128 deposit, uint128 withdraw) public {
        vm.assume(deposit > 0);
        withdraw = uint128(bound(withdraw, 1, deposit));

        token.mint(user1, deposit);

        vm.startPrank(user1);
        token.approve(address(vault), deposit);
        vault.deposit(address(token), deposit);

        assertEq(vault.getBalance(user1, address(token)), deposit);

        vault.withdraw(address(token), withdraw);
        assertEq(vault.getBalance(user1, address(token)), uint256(deposit) - withdraw);
        vm.stopPrank();
    }

    function testFuzz_Vault_ProtectionThreshold(uint64 threshold, uint64 risk) public {
        threshold = uint64(bound(threshold, 1, 100));
        risk = uint64(bound(risk, 0, 100));

        _setupUserWithDeposit(user1, 1000e18);

        vm.prank(user1);
        vault.createRule(PROTOCOL_A, threshold, address(token), safe);

        skip(5 minutes + 1);
        vm.prank(updater);
        oracle.updateScore(PROTOCOL_A, risk);

        vault.protect(user1);

        if (risk >= threshold) {
            assertEq(vault.getBalance(user1, address(token)), 0);
            assertEq(token.balanceOf(safe), 1000e18);
        } else {
            assertEq(vault.getBalance(user1, address(token)), 1000e18);
            assertEq(token.balanceOf(safe), 0);
        }
    }

    /*//////////////////////////////////////////////////////////////
                          INVARIANT TESTS
    //////////////////////////////////////////////////////////////*/

    function invariant_OracleScoresBounded() public view {
        uint256 count = oracle.protocolCount();
        for (uint256 i = 0; i < count; i++) {
            (bytes32[] memory ids,) = oracle.getProtocols(i, 1);
            if (ids.length > 0) {
                (uint64 score,,) = oracle.getScore(ids[0]);
                assertLe(score, 100);
            }
        }
    }

    function invariant_VaultBalanceConsistency() public view {
        uint256 vaultBal = token.balanceOf(address(vault));
        uint256 total = vault.totalUsers();

        uint256 sum;
        for (uint256 i = 0; i < total; i++) {
            (address[] memory users,) = vault.getUsers(i, 1);
            if (users.length > 0) {
                sum += vault.getBalance(users[0], address(token));
            }
        }

        assertGe(vaultBal, sum);
    }

    /*//////////////////////////////////////////////////////////////
                            HELPERS
    //////////////////////////////////////////////////////////////*/

    function _setupUserWithDeposit(address user, uint256 amount) internal {
        token.mint(user, amount);
        vm.startPrank(user);
        token.approve(address(vault), amount);
        vault.deposit(address(token), amount);
        vm.stopPrank();
    }
}
