// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {NexusRiskOracle} from "../src/NexusRiskOracle.sol";
import {ProtectionVault} from "../src/ProtectionVault.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @dev Minimal ERC20 for testing
contract Token is ERC20 {
    constructor() ERC20("TEST", "TEST") {}
    function mint(address to, uint256 amt) external { _mint(to, amt); }
}

/**
 * @title NexusFuzzTest
 * @notice Property-based fuzz testing for Nexus Protocol
 */
contract NexusFuzzTest is Test {
    NexusRiskOracle oracle;
    ProtectionVault vault;
    Token token;

    address user = makeAddr("user");
    address safe = makeAddr("safe");

    function setUp() public {
        oracle = new NexusRiskOracle();
        vault = new ProtectionVault(address(oracle));
        token = new Token();
    }

    /*//////////////////////////////////////////////////////////////
                           ORACLE FUZZ TESTS
    //////////////////////////////////////////////////////////////*/

    /// @notice Valid scores (0-100) always accepted
    function testFuzz_ValidScore(uint64 score) public {
        score = uint64(bound(score, 0, 100));
        bytes32 id = keccak256(abi.encodePacked("proto", score));

        oracle.updateRiskScore(id, score);
        (uint64 s,,) = oracle.getRiskScore(id);

        assertEq(s, score);
    }

    /// @notice Invalid scores (>100) always revert
    function testFuzz_InvalidScoreReverts(uint64 score) public {
        vm.assume(score > 100);

        vm.expectRevert(NexusRiskOracle.InvalidScore.selector);
        oracle.updateRiskScore(keccak256("x"), score);
    }

    /// @notice Protocol ID hashing is deterministic
    function testFuzz_IdConsistency(string memory name) public view {
        vm.assume(bytes(name).length > 0 && bytes(name).length < 64);

        bytes32 a = oracle.toProtocolId(name);
        bytes32 b = oracle.toProtocolId(name);

        assertEq(a, b);
        assertEq(a, keccak256(bytes(name)));
    }

    /// @notice Threshold boundary behavior
    function testFuzz_ThresholdBoundary(uint64 threshold, uint64 score) public {
        threshold = uint64(bound(threshold, 0, 100));
        score = uint64(bound(score, 0, 100));

        oracle.setAlertThreshold(threshold);

        bytes32 id = keccak256("boundary");
        oracle.updateRiskScore(id, score);

        bytes32[] memory high = oracle.getHighRiskProtocols();

        if (score >= threshold) {
            assertGe(high.length, 1);
        }
    }

    /// @notice Batch updates with random data
    function testFuzz_BatchUpdate(uint8 count, uint64 seed) public {
        count = uint8(bound(count, 1, 30));

        bytes32[] memory ids = new bytes32[](count);
        uint64[] memory scores = new uint64[](count);

        for (uint256 i; i < count; ++i) {
            ids[i] = keccak256(abi.encodePacked(seed, i));
            scores[i] = uint64((seed + i) % 101);
        }

        oracle.batchUpdateRiskScores(ids, scores);

        for (uint256 i; i < count; ++i) {
            (uint64 s,,) = oracle.getRiskScore(ids[i]);
            assertEq(s, scores[i]);
        }
        assertEq(oracle.getProtocolCount(), count);
    }

    /// @notice Staleness timing accuracy
    function testFuzz_Staleness(uint64 elapsed) public {
        elapsed = uint64(bound(elapsed, 0, 30 days));

        bytes32 id = keccak256("stale");
        oracle.updateRiskScore(id, 50);

        vm.warp(block.timestamp + elapsed);
        (,, bool stale) = oracle.getRiskScore(id);

        assertEq(stale, elapsed > 1 hours);
    }

    /*//////////////////////////////////////////////////////////////
                           VAULT FUZZ TESTS
    //////////////////////////////////////////////////////////////*/

    /// @notice Deposit/withdraw roundtrip
    function testFuzz_DepositWithdraw(uint128 amount) public {
        vm.assume(amount > 0);

        token.mint(user, amount);

        vm.startPrank(user);
        token.approve(address(vault), amount);
        vault.deposit(address(token), amount);

        assertEq(vault.getBalance(user, address(token)), amount);

        vault.withdraw(address(token), amount);
        assertEq(vault.getBalance(user, address(token)), 0);
        assertEq(token.balanceOf(user), amount);
        vm.stopPrank();
    }

    /// @notice Partial withdrawals maintain balance integrity
    function testFuzz_PartialWithdraw(uint128 deposit, uint64 w1, uint64 w2) public {
        vm.assume(deposit > 0);
        w1 = uint64(bound(w1, 1, deposit));
        w2 = uint64(bound(w2, 0, deposit - w1));

        token.mint(user, deposit);

        vm.startPrank(user);
        token.approve(address(vault), deposit);
        vault.deposit(address(token), deposit);

        vault.withdraw(address(token), w1);
        assertEq(vault.getBalance(user, address(token)), deposit - w1);

        if (w2 > 0) {
            vault.withdraw(address(token), w2);
            assertEq(vault.getBalance(user, address(token)), deposit - w1 - w2);
        }
        vm.stopPrank();
    }

    /// @notice Protection triggers exactly at threshold
    function testFuzz_ProtectionTrigger(uint64 threshold, uint64 risk) public {
        threshold = uint64(bound(threshold, 1, 100));
        risk = uint64(bound(risk, 0, 100));

        uint256 amt = 1000e18;
        token.mint(user, amt);

        vm.startPrank(user);
        token.approve(address(vault), amt);
        vault.deposit(address(token), amt);

        bytes32 id = keccak256("trigger");
        vault.addProtectionRule(id, threshold, address(token), safe);
        vm.stopPrank();

        oracle.updateRiskScore(id, risk);
        vault.checkAndProtect(user);

        if (risk >= threshold) {
            assertEq(vault.getBalance(user, address(token)), 0);
            assertEq(token.balanceOf(safe), amt);
        } else {
            assertEq(vault.getBalance(user, address(token)), amt);
            assertEq(token.balanceOf(safe), 0);
        }
    }

    /// @notice Multiple rules creation
    function testFuzz_MultipleRules(uint8 count, uint64 seed) public {
        count = uint8(bound(count, 1, 10));

        uint256 amt = 1000e18;
        token.mint(user, amt);

        vm.startPrank(user);
        token.approve(address(vault), amt);
        vault.deposit(address(token), amt);

        for (uint256 i; i < count; ++i) {
            bytes32 id = keccak256(abi.encodePacked(seed, i));
            uint64 t = uint64(50 + (i % 50));
            address r = makeAddr(string.concat("r", vm.toString(i)));
            vault.addProtectionRule(id, t, address(token), r);
        }
        vm.stopPrank();

        assertEq(vault.getRuleCount(user), count);
    }

    /// @notice Invalid threshold reverts
    function testFuzz_InvalidThreshold(uint64 threshold) public {
        vm.assume(threshold > 100);

        uint256 amt = 1000e18;
        token.mint(user, amt);

        vm.startPrank(user);
        token.approve(address(vault), amt);
        vault.deposit(address(token), amt);

        vm.expectRevert(ProtectionVault.InvalidThreshold.selector);
        vault.addProtectionRule(keccak256("x"), threshold, address(token), safe);
        vm.stopPrank();
    }
}

/**
 * @title NexusInvariantTest
 * @notice Invariant testing for system-wide guarantees
 */
contract NexusInvariantTest is Test {
    NexusRiskOracle oracle;
    ProtectionVault vault;
    Token token;
    Handler handler;

    address[] actors;

    function setUp() public {
        oracle = new NexusRiskOracle();
        vault = new ProtectionVault(address(oracle));
        token = new Token();

        for (uint256 i; i < 5; ++i) {
            address a = makeAddr(string.concat("actor", vm.toString(i)));
            actors.push(a);
            token.mint(a, 10000e18);
        }

        handler = new Handler(oracle, vault, token, actors);

        // Authorize handler to update oracle
        oracle.addAuthorizedUpdater(address(handler));

        targetContract(address(handler));
    }

    /// @notice Vault balance ≥ sum of user balances
    function invariant_BalanceConsistency() public view {
        uint256 vaultBal = token.balanceOf(address(vault));
        uint256 sum;
        for (uint256 i; i < actors.length; ++i) {
            sum += vault.getBalance(actors[i], address(token));
        }
        assertGe(vaultBal, sum);
    }

    /// @notice All scores bounded 0-100
    function invariant_ScoresBounded() public view {
        uint256 n = oracle.getProtocolCount();
        for (uint256 i; i < n; ++i) {
            (uint64 s,,) = oracle.getRiskScore(oracle.protocolIds(i));
            assertLe(s, 100);
        }
    }

    /// @notice Alert threshold always valid
    function invariant_ThresholdValid() public view {
        assertLe(oracle.alertThreshold(), 100);
    }

    /// @notice Protocol tracking consistent
    function invariant_ProtocolTracking() public view {
        uint256 n = oracle.getProtocolCount();
        for (uint256 i; i < n; ++i) {
            assertTrue(oracle.isTracked(oracle.protocolIds(i)));
        }
    }

    /// @notice User tracking consistent
    function invariant_UserTracking() public view {
        uint256 n = vault.getTotalUsers();
        for (uint256 i; i < n; ++i) {
            assertTrue(vault.hasVault(vault.users(i)));
        }
    }
}

/**
 * @title Handler
 * @notice Bounded action handler for invariant testing
 */
contract Handler is Test {
    NexusRiskOracle oracle;
    ProtectionVault vault;
    Token token;
    address[] actors;
    bytes32[] pids;

    constructor(
        NexusRiskOracle _oracle,
        ProtectionVault _vault,
        Token _token,
        address[] memory _actors
    ) {
        oracle = _oracle;
        vault = _vault;
        token = _token;
        actors = _actors;

        for (uint256 i; i < 5; ++i) {
            pids.push(keccak256(abi.encodePacked("p", i)));
        }
    }

    function deposit(uint256 actorSeed, uint256 amount) external {
        address a = actors[actorSeed % actors.length];
        amount = bound(amount, 1, 1000e18);

        vm.startPrank(a);
        token.approve(address(vault), amount);
        vault.deposit(address(token), amount);
        vm.stopPrank();
    }

    function withdraw(uint256 actorSeed, uint256 amount) external {
        address a = actors[actorSeed % actors.length];
        uint256 bal = vault.getBalance(a, address(token));
        if (bal == 0) return;

        amount = bound(amount, 1, bal);
        vm.prank(a);
        vault.withdraw(address(token), amount);
    }

    function addRule(uint256 actorSeed, uint256 pidSeed, uint64 threshold) external {
        address a = actors[actorSeed % actors.length];
        if (!vault.hasVault(a)) return;

        bytes32 id = pids[pidSeed % pids.length];
        threshold = uint64(bound(threshold, 1, 100));
        address safe = makeAddr(string.concat("s", vm.toString(actorSeed)));

        vm.prank(a);
        vault.addProtectionRule(id, threshold, address(token), safe);
    }

    function updateScore(uint256 pidSeed, uint64 score) external {
        bytes32 id = pids[pidSeed % pids.length];
        score = uint64(bound(score, 0, 100));
        oracle.updateRiskScore(id, score);
    }

    function protect(uint256 actorSeed) external {
        address a = actors[actorSeed % actors.length];
        if (!vault.hasVault(a)) return;
        vault.checkAndProtect(a);
    }
}
