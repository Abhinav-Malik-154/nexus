// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {NexusRiskOracle} from "./NexusRiskOracle.sol";

/**
 * @title ProtectionVault
 * @author Nexus Protocol
 * @notice Autonomous vault protecting user funds via AI risk detection
 * @dev
 *   ┌─────────────────────────────────────────────────────────────────┐
 *   │  USER FLOW                                                      │
 *   │  ───────────────────────────────────────────────────────────── │
 *   │  1. deposit(token, amount)                                      │
 *   │  2. addProtectionRule(protocol, threshold, token, safeAddr)     │
 *   │  3. Chainlink → checkUpkeep() → performUpkeep()                 │
 *   │  4. Risk ≥ Threshold → Auto-transfer to safe address           │
 *   └─────────────────────────────────────────────────────────────────┘
 *
 *   GAS OPTIMIZATIONS:
 *   - bytes32 protocol IDs (matches Oracle)
 *   - Packed ProtectionRule struct
 *   - Cached storage reads in loops
 *   - Unchecked increments
 */
contract ProtectionVault is ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    /*//////////////////////////////////////////////////////////////
                                 ERRORS
    //////////////////////////////////////////////////////////////*/

    error ZeroAmount();
    error ZeroAddress();
    error InvalidThreshold();
    error NoVault();
    error InsufficientBalance();
    error InvalidIndex();

    /*//////////////////////////////////////////////////////////////
                                 EVENTS
    //////////////////////////////////////////////////////////////*/

    event Deposited(address indexed user, address indexed token, uint256 amount);
    event Withdrawn(address indexed user, address indexed token, uint256 amount, address to);
    event RuleAdded(
        address indexed user,
        bytes32 indexed protocolId,
        uint64 threshold,
        address token,
        address safeAddress
    );
    event RuleDeactivated(address indexed user, uint256 index);
    event ProtectionTriggered(
        address indexed user,
        bytes32 indexed protocolId,
        uint64 riskScore,
        address token,
        uint256 amount,
        address safeAddress
    );

    /*//////////////////////////////////////////////////////////////
                                 TYPES
    //////////////////////////////////////////////////////////////*/

    /// @dev Packed: protocolId(32) | token(20) + threshold(8) + flags(1) | safeAddr(20) + createdAt(8)
    struct ProtectionRule {
        bytes32 protocolId;
        address token;
        uint64 riskThreshold;
        uint8 flags;         // Bit 0: isActive
        address safeAddress;
        uint64 createdAt;
    }

    struct UserVault {
        mapping(address => uint256) balances;
        ProtectionRule[] rules;
        bool exists;
    }

    /*//////////////////////////////////////////////////////////////
                                 STATE
    //////////////////////////////////////////////////////////////*/

    NexusRiskOracle public immutable oracle;
    mapping(address => UserVault) internal _vaults;
    address[] public users;

    /*//////////////////////////////////////////////////////////////
                              CONSTRUCTOR
    //////////////////////////////////////////////////////////////*/

    constructor(address _oracle) Ownable(msg.sender) {
        if (_oracle == address(0)) revert ZeroAddress();
        oracle = NexusRiskOracle(_oracle);
    }

    /*//////////////////////////////////////////////////////////////
                            CORE FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Deposit tokens into vault
    function deposit(address token, uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (token == address(0)) revert ZeroAddress();

        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);

        UserVault storage v = _vaults[msg.sender];
        if (!v.exists) {
            users.push(msg.sender);
            v.exists = true;
        }
        unchecked { v.balances[token] += amount; }

        emit Deposited(msg.sender, token, amount);
    }

    /// @notice Withdraw tokens from vault
    function withdraw(address token, uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        UserVault storage v = _vaults[msg.sender];
        uint256 bal = v.balances[token];
        if (bal < amount) revert InsufficientBalance();

        unchecked { v.balances[token] = bal - amount; }
        IERC20(token).safeTransfer(msg.sender, amount);

        emit Withdrawn(msg.sender, token, amount, msg.sender);
    }

    /// @notice Add protection rule for a protocol
    function addProtectionRule(
        bytes32 protocolId,
        uint64 threshold,
        address token,
        address safeAddr
    ) external {
        if (threshold > 100) revert InvalidThreshold();
        if (safeAddr == address(0) || token == address(0)) revert ZeroAddress();

        UserVault storage v = _vaults[msg.sender];
        if (!v.exists) revert NoVault();

        v.rules.push(ProtectionRule({
            protocolId: protocolId,
            token: token,
            riskThreshold: threshold,
            flags: 1,
            safeAddress: safeAddr,
            createdAt: uint64(block.timestamp)
        }));

        emit RuleAdded(msg.sender, protocolId, threshold, token, safeAddr);
    }

    /// @notice Add rule by protocol name
    function addProtectionRuleByName(
        string calldata name,
        uint64 threshold,
        address token,
        address safeAddr
    ) external {
        if (threshold > 100) revert InvalidThreshold();
        if (safeAddr == address(0) || token == address(0)) revert ZeroAddress();

        UserVault storage v = _vaults[msg.sender];
        if (!v.exists) revert NoVault();

        bytes32 id = oracle.toProtocolId(name);
        v.rules.push(ProtectionRule({
            protocolId: id,
            token: token,
            riskThreshold: threshold,
            flags: 1,
            safeAddress: safeAddr,
            createdAt: uint64(block.timestamp)
        }));

        emit RuleAdded(msg.sender, id, threshold, token, safeAddr);
    }

    /// @notice Deactivate a rule
    function deactivateRule(uint256 index) external {
        UserVault storage v = _vaults[msg.sender];
        if (index >= v.rules.length) revert InvalidIndex();
        v.rules[index].flags &= ~uint8(1);
        emit RuleDeactivated(msg.sender, index);
    }

    /// @notice Execute protection check for a user (permissionless)
    function checkAndProtect(address user) external nonReentrant {
        _protect(user);
    }

    /// @notice Batch protection check
    function batchCheckAndProtect(address[] calldata _users) external nonReentrant {
        uint256 len = _users.length;
        for (uint256 i; i < len;) {
            _protect(_users[i]);
            unchecked { ++i; }
        }
    }

    /*//////////////////////////////////////////////////////////////
                       CHAINLINK AUTOMATION
    //////////////////////////////////////////////////////////////*/

    /// @notice Chainlink checkUpkeep compatible
    function checkUpkeep(bytes calldata) external view returns (bool needed, bytes memory data) {
        uint256 len = users.length;
        address[] memory pending = new address[](len);
        uint256 count;

        for (uint256 i; i < len;) {
            if (_needsProtection(users[i])) {
                pending[count] = users[i];
                unchecked { ++count; }
            }
            unchecked { ++i; }
        }

        if (count > 0) {
            assembly { mstore(pending, count) }
            return (true, abi.encode(pending));
        }
    }

    /// @notice Chainlink performUpkeep compatible
    function performUpkeep(bytes calldata data) external nonReentrant {
        address[] memory toProtect = abi.decode(data, (address[]));
        uint256 len = toProtect.length;
        for (uint256 i; i < len;) {
            _protect(toProtect[i]);
            unchecked { ++i; }
        }
    }

    /*//////////////////////////////////////////////////////////////
                            VIEW FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function getBalance(address user, address token) external view returns (uint256) {
        return _vaults[user].balances[token];
    }

    function getRules(address user) external view returns (ProtectionRule[] memory) {
        return _vaults[user].rules;
    }

    function getRuleCount(address user) external view returns (uint256) {
        return _vaults[user].rules.length;
    }

    function hasVault(address user) external view returns (bool) {
        return _vaults[user].exists;
    }

    function getTotalUsers() external view returns (uint256) {
        return users.length;
    }

    /*//////////////////////////////////////////////////////////////
                          INTERNAL FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function _needsProtection(address user) internal view returns (bool) {
        UserVault storage v = _vaults[user];
        if (!v.exists) return false;

        ProtectionRule[] storage rules = v.rules;
        uint256 len = rules.length;

        for (uint256 i; i < len;) {
            ProtectionRule storage r = rules[i];
            if (r.flags & 1 == 1 && v.balances[r.token] > 0) {
                (uint64 risk,, bool stale) = oracle.getRiskScore(r.protocolId);
                if (!stale && risk >= r.riskThreshold) return true;
            }
            unchecked { ++i; }
        }
        return false;
    }

    function _protect(address user) internal {
        UserVault storage v = _vaults[user];
        if (!v.exists) return;

        ProtectionRule[] storage rules = v.rules;
        uint256 len = rules.length;

        for (uint256 i; i < len;) {
            ProtectionRule storage r = rules[i];

            // Skip inactive
            if (r.flags & 1 == 0) { unchecked { ++i; } continue; }

            address token = r.token;
            uint256 bal = v.balances[token];
            if (bal == 0) { unchecked { ++i; } continue; }

            (uint64 risk,, bool stale) = oracle.getRiskScore(r.protocolId);
            if (stale) { unchecked { ++i; } continue; }

            if (risk >= r.riskThreshold) {
                // Cache before state change (CEI)
                address safe = r.safeAddress;
                bytes32 pid = r.protocolId;

                // Update state
                v.balances[token] = 0;
                r.flags = 0;

                // External call
                IERC20(token).safeTransfer(safe, bal);
                emit ProtectionTriggered(user, pid, risk, token, bal, safe);
            }
            unchecked { ++i; }
        }
    }
}
