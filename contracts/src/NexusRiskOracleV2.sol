// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";

/**
 * @title NexusRiskOracleV2
 * @author Nexus Protocol
 * @notice Production-grade upgradeable oracle for AI-generated DeFi risk scores
 * @dev
 *   SECURITY FEATURES:
 *   - UUPS upgradeable (future-proof)
 *   - Role-based access control (UPDATER, PAUSER, ADMIN)
 *   - Pausable (emergency circuit breaker)
 *   - Rate limiting (prevent spam updates)
 *   - Timelock for threshold changes
 *   - Paginated queries (gas-safe at scale)
 *
 *   GAS OPTIMIZATIONS:
 *   - bytes32 protocol IDs
 *   - Packed structs (single slot)
 *   - Unchecked increments
 *   - Cached storage reads
 */
contract NexusRiskOracleV2 is
    Initializable,
    UUPSUpgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable
{
    /*//////////////////////////////////////////////////////////////
                               CONSTANTS
    //////////////////////////////////////////////////////////////*/

    bytes32 public constant UPDATER_ROLE = keccak256("UPDATER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint64 internal constant MAX_SCORE = 100;
    uint64 internal constant STALENESS_PERIOD = 1 hours;
    uint64 internal constant MIN_UPDATE_INTERVAL = 5 minutes;
    uint64 internal constant TIMELOCK_DELAY = 24 hours;

    /*//////////////////////////////////////////////////////////////
                                ERRORS
    //////////////////////////////////////////////////////////////*/

    error InvalidScore();
    error InvalidThreshold();
    error ArrayMismatch();
    error EmptyArray();
    error TooLarge();
    error RateLimited();
    error TimelockActive();
    error TimelockNotReady();
    error NoTimelockPending();

    /*//////////////////////////////////////////////////////////////
                                EVENTS
    //////////////////////////////////////////////////////////////*/

    event ScoreUpdated(bytes32 indexed id, uint64 oldScore, uint64 newScore, uint64 ts);
    event HighRisk(bytes32 indexed id, uint64 score, uint64 ts);
    event ThresholdQueued(uint64 newThreshold, uint64 executeAfter);
    event ThresholdUpdated(uint64 oldThreshold, uint64 newThreshold);
    event ProtocolAdded(bytes32 indexed id, string name);

    /*//////////////////////////////////////////////////////////////
                                STRUCTS
    //////////////////////////////////////////////////////////////*/

    /// @dev Packed: score(64) + lastUpdated(64) + flags(8) = 136 bits < 256
    struct RiskData {
        uint64 score;
        uint64 lastUpdated;
        uint8 flags; // bit0: tracked
    }

    struct TimelockOp {
        uint64 newThreshold;
        uint64 executeAfter;
    }

    /*//////////////////////////////////////////////////////////////
                                STORAGE
    //////////////////////////////////////////////////////////////*/

    mapping(bytes32 => RiskData) internal _data;
    mapping(bytes32 => string) public names;
    bytes32[] internal _ids;

    uint64 public alertThreshold;
    uint64 public lastGlobalUpdate;

    TimelockOp public pendingThreshold;

    /// @dev Gap for future upgrades
    uint256[44] private __gap;

    /*//////////////////////////////////////////////////////////////
                             INITIALIZER
    //////////////////////////////////////////////////////////////*/

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address admin) external initializer {
        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(UPDATER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        alertThreshold = 70;
    }

    /*//////////////////////////////////////////////////////////////
                           WRITE FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Update single score
    function updateScore(bytes32 id, uint64 score) external onlyRole(UPDATER_ROLE) whenNotPaused {
        _enforceRateLimit();
        _update(id, score);
    }

    /// @notice Update by name (stores name on first use)
    function updateScoreByName(string calldata name, uint64 score)
        external
        onlyRole(UPDATER_ROLE)
        whenNotPaused
    {
        _enforceRateLimit();
        bytes32 id = keccak256(bytes(name));
        if (bytes(names[id]).length == 0) {
            names[id] = name;
            emit ProtocolAdded(id, name);
        }
        _update(id, score);
    }

    /// @notice Batch update (max 100 per call for gas safety)
    function batchUpdate(bytes32[] calldata ids, uint64[] calldata scores)
        external
        onlyRole(UPDATER_ROLE)
        whenNotPaused
    {
        uint256 len = ids.length;
        if (len == 0) revert EmptyArray();
        if (len != scores.length) revert ArrayMismatch();
        if (len > 100) revert TooLarge();

        _enforceRateLimit();

        for (uint256 i; i < len; ) {
            _update(ids[i], scores[i]);
            unchecked { ++i; }
        }
    }

    /// @notice Batch update by names
    function batchUpdateByName(string[] calldata _names, uint64[] calldata scores)
        external
        onlyRole(UPDATER_ROLE)
        whenNotPaused
    {
        uint256 len = _names.length;
        if (len == 0) revert EmptyArray();
        if (len != scores.length) revert ArrayMismatch();
        if (len > 100) revert TooLarge();

        _enforceRateLimit();

        for (uint256 i; i < len; ) {
            bytes32 id = keccak256(bytes(_names[i]));
            if (bytes(names[id]).length == 0) {
                names[id] = _names[i];
                emit ProtocolAdded(id, _names[i]);
            }
            _update(id, scores[i]);
            unchecked { ++i; }
        }
    }

    /*//////////////////////////////////////////////////////////////
                           VIEW FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Get score with staleness check
    function getScore(bytes32 id) external view returns (uint64 score, uint64 lastUpdated, bool stale) {
        RiskData storage d = _data[id];
        return (d.score, d.lastUpdated, block.timestamp > d.lastUpdated + STALENESS_PERIOD);
    }

    /// @notice Get score by name
    function getScoreByName(string calldata name) external view returns (uint64, uint64, bool) {
        RiskData storage d = _data[keccak256(bytes(name))];
        return (d.score, d.lastUpdated, block.timestamp > d.lastUpdated + STALENESS_PERIOD);
    }

    /// @notice Check if any protocol is high risk
    function hasHighRisk() external view returns (bool) {
        uint256 len = _ids.length;
        uint64 t = alertThreshold;
        for (uint256 i; i < len; ) {
            if (_data[_ids[i]].score >= t) return true;
            unchecked { ++i; }
        }
        return false;
    }

    /// @notice Get high risk protocols (paginated)
    function getHighRisk(uint256 offset, uint256 limit)
        external
        view
        returns (bytes32[] memory result, uint256 total)
    {
        uint256 len = _ids.length;
        uint64 t = alertThreshold;

        // Count total high risk
        for (uint256 i; i < len; ) {
            if (_data[_ids[i]].score >= t) ++total;
            unchecked { ++i; }
        }

        if (total == 0 || offset >= total) return (new bytes32[](0), total);

        uint256 size = limit;
        if (offset + size > total) size = total - offset;

        result = new bytes32[](size);
        uint256 found;
        uint256 idx;

        for (uint256 i; i < len && idx < size; ) {
            if (_data[_ids[i]].score >= t) {
                if (found >= offset) {
                    result[idx] = _ids[i];
                    ++idx;
                }
                ++found;
            }
            unchecked { ++i; }
        }
    }

    /// @notice Get all protocols (paginated)
    function getProtocols(uint256 offset, uint256 limit)
        external
        view
        returns (bytes32[] memory result, uint256 total)
    {
        total = _ids.length;
        if (total == 0 || offset >= total) return (new bytes32[](0), total);

        uint256 size = limit;
        if (offset + size > total) size = total - offset;

        result = new bytes32[](size);
        for (uint256 i; i < size; ) {
            result[i] = _ids[offset + i];
            unchecked { ++i; }
        }
    }

    function protocolCount() external view returns (uint256) {
        return _ids.length;
    }

    function isTracked(bytes32 id) external view returns (bool) {
        return _data[id].flags & 1 == 1;
    }

    function toId(string memory name) external pure returns (bytes32) {
        return keccak256(bytes(name));
    }

    /*//////////////////////////////////////////////////////////////
                         ADMIN FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Queue threshold change (24h timelock)
    function queueThreshold(uint64 threshold) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (threshold > MAX_SCORE) revert InvalidThreshold();
        if (pendingThreshold.executeAfter != 0) revert TimelockActive();

        uint64 executeAfter = uint64(block.timestamp) + TIMELOCK_DELAY;
        pendingThreshold = TimelockOp(threshold, executeAfter);
        emit ThresholdQueued(threshold, executeAfter);
    }

    /// @notice Execute threshold change after timelock
    function executeThreshold() external onlyRole(DEFAULT_ADMIN_ROLE) {
        TimelockOp memory op = pendingThreshold;
        if (op.executeAfter == 0) revert NoTimelockPending();
        if (block.timestamp < op.executeAfter) revert TimelockNotReady();

        uint64 old = alertThreshold;
        alertThreshold = op.newThreshold;
        delete pendingThreshold;
        emit ThresholdUpdated(old, op.newThreshold);
    }

    /// @notice Cancel pending threshold change
    function cancelThreshold() external onlyRole(DEFAULT_ADMIN_ROLE) {
        delete pendingThreshold;
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

    function _update(bytes32 id, uint64 score) internal {
        if (score > MAX_SCORE) revert InvalidScore();

        RiskData storage d = _data[id];
        uint64 old = d.score;
        uint64 ts = uint64(block.timestamp);

        d.score = score;
        d.lastUpdated = ts;

        if (d.flags & 1 == 0) {
            d.flags = 1;
            _ids.push(id);
        }

        emit ScoreUpdated(id, old, score, ts);
        if (score >= alertThreshold) emit HighRisk(id, score, ts);
    }

    function _enforceRateLimit() internal {
        if (block.timestamp < lastGlobalUpdate + MIN_UPDATE_INTERVAL) revert RateLimited();
        lastGlobalUpdate = uint64(block.timestamp);
    }

    function _authorizeUpgrade(address) internal override onlyRole(DEFAULT_ADMIN_ROLE) {}
}
