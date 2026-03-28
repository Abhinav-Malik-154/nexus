// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

interface INexusOracle {
    function getScore(bytes32 id) external view returns (uint64 score, uint64 lastUpdated, bool stale);
    function toId(string memory name) external pure returns (bytes32);
}

/**
 * @title ProtectionVaultV2
 * @author Nexus Protocol
 * @notice Production-grade autonomous vault protecting funds via AI risk detection
 * @dev
 *   SECURITY FEATURES:
 *   - UUPS upgradeable
 *   - Role-based access (KEEPER, PAUSER, ADMIN)
 *   - Pausable with emergency withdrawal
 *   - ReentrancyGuard on all external calls
 *   - Paginated iteration (gas-safe at scale)
 *
 *   SCALABILITY:
 *   - EnumerableSet-style user tracking with O(1) add/remove
 *   - Configurable batch size for Chainlink Automation
 *   - Cursor-based checkUpkeep for large user sets
 *
 *   GAS OPTIMIZATIONS:
 *   - Packed structs
 *   - Unchecked increments
 *   - Cached storage reads
 */
contract ProtectionVaultV2 is
    Initializable,
    UUPSUpgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard
{
    using SafeERC20 for IERC20;

    /*//////////////////////////////////////////////////////////////
                               CONSTANTS
    //////////////////////////////////////////////////////////////*/

    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint256 internal constant MAX_RULES_PER_USER = 20;
    uint256 internal constant MAX_BATCH_SIZE = 50;

    /*//////////////////////////////////////////////////////////////
                                ERRORS
    //////////////////////////////////////////////////////////////*/

    error ZeroAmount();
    error ZeroAddress();
    error InvalidThreshold();
    error NoVault();
    error InsufficientBalance();
    error TooManyRules();
    error InvalidIndex();
    error AlreadyActive();
    error NotActive();

    /*//////////////////////////////////////////////////////////////
                                EVENTS
    //////////////////////////////////////////////////////////////*/

    event Deposited(address indexed user, address indexed token, uint256 amount);
    event Withdrawn(address indexed user, address indexed token, uint256 amount);
    event RuleCreated(address indexed user, uint256 indexed ruleId, bytes32 protocolId, uint64 threshold);
    event RuleToggled(address indexed user, uint256 indexed ruleId, bool active);
    event Protected(
        address indexed user,
        bytes32 indexed protocolId,
        uint64 risk,
        address token,
        uint256 amount,
        address safe
    );
    event OracleUpdated(address oldOracle, address newOracle);
    event BatchSizeUpdated(uint256 oldSize, uint256 newSize);

    /*//////////////////////////////////////////////////////////////
                                STRUCTS
    //////////////////////////////////////////////////////////////*/

    /// @dev Packed into ~2 slots
    struct Rule {
        bytes32 protocolId;
        address token;
        address safe;
        uint64 threshold;
        uint64 createdAt;
        bool active;
    }

    struct Vault {
        mapping(address => uint256) balances;
        Rule[] rules;
        bool exists;
    }

    /*//////////////////////////////////////////////////////////////
                                STORAGE
    //////////////////////////////////////////////////////////////*/

    INexusOracle public oracle;

    mapping(address => Vault) internal _vaults;

    // EnumerableSet-style user tracking
    address[] internal _users;
    mapping(address => uint256) internal _userIndex; // index + 1 (0 = not exists)

    // Automation config
    uint256 public batchSize;
    uint256 public cursor; // for round-robin checkUpkeep

    /// @dev Gap for future upgrades
    uint256[43] private __gap;

    /*//////////////////////////////////////////////////////////////
                             INITIALIZER
    //////////////////////////////////////////////////////////////*/

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _oracle, address admin) external initializer {
        if (_oracle == address(0) || admin == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(KEEPER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        oracle = INexusOracle(_oracle);
        batchSize = 20;
    }

    /*//////////////////////////////////////////////////////////////
                           CORE FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Deposit tokens
    function deposit(address token, uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();
        if (token == address(0)) revert ZeroAddress();

        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);

        Vault storage v = _vaults[msg.sender];
        if (!v.exists) {
            _addUser(msg.sender);
            v.exists = true;
        }

        unchecked { v.balances[token] += amount; }
        emit Deposited(msg.sender, token, amount);
    }

    /// @notice Withdraw tokens
    function withdraw(address token, uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();

        Vault storage v = _vaults[msg.sender];
        uint256 bal = v.balances[token];
        if (bal < amount) revert InsufficientBalance();

        unchecked { v.balances[token] = bal - amount; }
        IERC20(token).safeTransfer(msg.sender, amount);
        emit Withdrawn(msg.sender, token, amount);
    }

    /// @notice Emergency withdraw (bypasses pause, but still reentrancy safe)
    function emergencyWithdraw(address token) external nonReentrant {
        Vault storage v = _vaults[msg.sender];
        uint256 bal = v.balances[token];
        if (bal == 0) revert InsufficientBalance();

        v.balances[token] = 0;
        IERC20(token).safeTransfer(msg.sender, bal);
        emit Withdrawn(msg.sender, token, bal);
    }

    /*//////////////////////////////////////////////////////////////
                          RULE MANAGEMENT
    //////////////////////////////////////////////////////////////*/

    /// @notice Create protection rule
    function createRule(
        bytes32 protocolId,
        uint64 threshold,
        address token,
        address safe
    ) external whenNotPaused returns (uint256 ruleId) {
        if (threshold > 100) revert InvalidThreshold();
        if (safe == address(0) || token == address(0)) revert ZeroAddress();

        Vault storage v = _vaults[msg.sender];
        if (!v.exists) revert NoVault();
        if (v.rules.length >= MAX_RULES_PER_USER) revert TooManyRules();

        ruleId = v.rules.length;
        v.rules.push(Rule({
            protocolId: protocolId,
            token: token,
            safe: safe,
            threshold: threshold,
            createdAt: uint64(block.timestamp),
            active: true
        }));

        emit RuleCreated(msg.sender, ruleId, protocolId, threshold);
    }

    /// @notice Create rule by protocol name
    function createRuleByName(
        string calldata name,
        uint64 threshold,
        address token,
        address safe
    ) external whenNotPaused returns (uint256) {
        return this.createRule(oracle.toId(name), threshold, token, safe);
    }

    /// @notice Activate rule
    function activateRule(uint256 ruleId) external whenNotPaused {
        Vault storage v = _vaults[msg.sender];
        if (ruleId >= v.rules.length) revert InvalidIndex();
        if (v.rules[ruleId].active) revert AlreadyActive();

        v.rules[ruleId].active = true;
        emit RuleToggled(msg.sender, ruleId, true);
    }

    /// @notice Deactivate rule
    function deactivateRule(uint256 ruleId) external whenNotPaused {
        Vault storage v = _vaults[msg.sender];
        if (ruleId >= v.rules.length) revert InvalidIndex();
        if (!v.rules[ruleId].active) revert NotActive();

        v.rules[ruleId].active = false;
        emit RuleToggled(msg.sender, ruleId, false);
    }

    /*//////////////////////////////////////////////////////////////
                       PROTECTION EXECUTION
    //////////////////////////////////////////////////////////////*/

    /// @notice Execute protection for single user (permissionless)
    function protect(address user) external nonReentrant whenNotPaused {
        _protect(user);
    }

    /// @notice Batch protection
    function protectBatch(address[] calldata users) external nonReentrant whenNotPaused {
        uint256 len = users.length;
        for (uint256 i; i < len; ) {
            _protect(users[i]);
            unchecked { ++i; }
        }
    }

    /*//////////////////////////////////////////////////////////////
                       CHAINLINK AUTOMATION
    //////////////////////////////////////////////////////////////*/

    /// @notice Check if upkeep needed (paginated, gas-safe)
    function checkUpkeep(bytes calldata)
        external
        view
        returns (bool needed, bytes memory data)
    {
        uint256 total = _users.length;
        if (total == 0) return (false, "");

        uint256 start = cursor % total;
        uint256 checked;
        uint256 count;
        address[] memory pending = new address[](batchSize);

        for (uint256 i; checked < total && count < batchSize; ) {
            uint256 idx = (start + i) % total;
            address user = _users[idx];

            if (_needsProtection(user)) {
                pending[count] = user;
                unchecked { ++count; }
            }

            unchecked { ++i; ++checked; }
        }

        if (count > 0) {
            assembly { mstore(pending, count) }
            return (true, abi.encode(pending));
        }
    }

    /// @notice Perform upkeep
    function performUpkeep(bytes calldata data) external nonReentrant onlyRole(KEEPER_ROLE) whenNotPaused {
        address[] memory users = abi.decode(data, (address[]));
        uint256 len = users.length;

        for (uint256 i; i < len; ) {
            _protect(users[i]);
            unchecked { ++i; }
        }

        // Advance cursor
        unchecked { cursor += batchSize; }
    }

    /*//////////////////////////////////////////////////////////////
                           VIEW FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function getBalance(address user, address token) external view returns (uint256) {
        return _vaults[user].balances[token];
    }

    function getRules(address user) external view returns (Rule[] memory) {
        return _vaults[user].rules;
    }

    function getRule(address user, uint256 ruleId) external view returns (Rule memory) {
        return _vaults[user].rules[ruleId];
    }

    function ruleCount(address user) external view returns (uint256) {
        return _vaults[user].rules.length;
    }

    function hasVault(address user) external view returns (bool) {
        return _vaults[user].exists;
    }

    function totalUsers() external view returns (uint256) {
        return _users.length;
    }

    /// @notice Get users (paginated)
    function getUsers(uint256 offset, uint256 limit)
        external
        view
        returns (address[] memory result, uint256 total)
    {
        total = _users.length;
        if (total == 0 || offset >= total) return (new address[](0), total);

        uint256 size = limit;
        if (offset + size > total) size = total - offset;

        result = new address[](size);
        for (uint256 i; i < size; ) {
            result[i] = _users[offset + i];
            unchecked { ++i; }
        }
    }

    /*//////////////////////////////////////////////////////////////
                         ADMIN FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function setOracle(address _oracle) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_oracle == address(0)) revert ZeroAddress();
        emit OracleUpdated(address(oracle), _oracle);
        oracle = INexusOracle(_oracle);
    }

    function setBatchSize(uint256 _size) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_size == 0 || _size > MAX_BATCH_SIZE) revert InvalidThreshold();
        emit BatchSizeUpdated(batchSize, _size);
        batchSize = _size;
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    /*//////////////////////////////////////////////////////////////
                        INTERNAL FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function _needsProtection(address user) internal view returns (bool) {
        Vault storage v = _vaults[user];
        if (!v.exists) return false;

        Rule[] storage rules = v.rules;
        uint256 len = rules.length;

        for (uint256 i; i < len; ) {
            Rule storage r = rules[i];
            if (r.active && v.balances[r.token] > 0) {
                (uint64 risk,, bool stale) = oracle.getScore(r.protocolId);
                if (!stale && risk >= r.threshold) return true;
            }
            unchecked { ++i; }
        }
        return false;
    }

    function _protect(address user) internal {
        Vault storage v = _vaults[user];
        if (!v.exists) return;

        Rule[] storage rules = v.rules;
        uint256 len = rules.length;

        for (uint256 i; i < len; ) {
            Rule storage r = rules[i];

            if (!r.active) {
                unchecked { ++i; }
                continue;
            }

            address token = r.token;
            uint256 bal = v.balances[token];

            if (bal == 0) {
                unchecked { ++i; }
                continue;
            }

            (uint64 risk,, bool stale) = oracle.getScore(r.protocolId);

            if (stale) {
                unchecked { ++i; }
                continue;
            }

            if (risk >= r.threshold) {
                // Cache before state changes (CEI)
                address safe = r.safe;
                bytes32 pid = r.protocolId;

                // State changes
                v.balances[token] = 0;
                r.active = false;

                // External call
                IERC20(token).safeTransfer(safe, bal);
                emit Protected(user, pid, risk, token, bal, safe);
            }

            unchecked { ++i; }
        }
    }

    function _addUser(address user) internal {
        if (_userIndex[user] == 0) {
            _users.push(user);
            _userIndex[user] = _users.length;
        }
    }

    // Optional: O(1) user removal (swap-and-pop)
    function _removeUser(address user) internal {
        uint256 idx = _userIndex[user];
        if (idx == 0) return;

        uint256 lastIdx = _users.length;
        if (idx != lastIdx) {
            address last = _users[lastIdx - 1];
            _users[idx - 1] = last;
            _userIndex[last] = idx;
        }

        _users.pop();
        delete _userIndex[user];
    }

    function _authorizeUpgrade(address) internal override onlyRole(DEFAULT_ADMIN_ROLE) {}
}
