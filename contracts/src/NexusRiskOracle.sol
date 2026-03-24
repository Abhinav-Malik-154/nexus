// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title NexusRiskOracle
 * @author Nexus Protocol
 * @notice Gas-optimized oracle for AI-generated DeFi risk scores
 * @dev
 *   ┌─────────────────────────────────────────────────────────────────┐
 *   │  ARCHITECTURE                                                   │
 *   │  ───────────────────────────────────────────────────────────── │
 *   │  GNN Model → Backend → batchUpdateRiskScores() → On-chain      │
 *   │                           ↓                                     │
 *   │                    ProtectionVault.checkUpkeep()                │
 *   └─────────────────────────────────────────────────────────────────┘
 *
 *   GAS OPTIMIZATIONS:
 *   - bytes32 protocol IDs vs strings (~2-5k gas/op)
 *   - Packed RiskData struct (single 256-bit slot)
 *   - Custom errors vs require strings (~200 gas)
 *   - Unchecked increments (~60 gas/iteration)
 *   - Cached storage reads in loops
 */
contract NexusRiskOracle is Ownable {
    /*//////////////////////////////////////////////////////////////
                                CONSTANTS
    //////////////////////////////////////////////////////////////*/

    /// @dev Max score (0-100, integer for gas efficiency)
    uint64 internal constant _MAX_SCORE = 100;

    /// @dev Staleness threshold (1 hour)
    uint64 internal constant _STALENESS = 1 hours;

    /*//////////////////////////////////////////////////////////////
                                 ERRORS
    //////////////////////////////////////////////////////////////*/

    error Unauthorized();
    error InvalidScore();
    error InvalidThreshold();
    error ArrayLengthMismatch();
    error EmptyArray();

    /*//////////////////////////////////////////////////////////////
                                 EVENTS
    //////////////////////////////////////////////////////////////*/

    event RiskScoreUpdated(
        bytes32 indexed protocolId,
        uint64 oldScore,
        uint64 newScore,
        uint64 timestamp
    );
    event HighRiskAlert(bytes32 indexed protocolId, uint64 score, uint64 timestamp);
    event ThresholdUpdated(uint64 oldThreshold, uint64 newThreshold);
    event UpdaterAdded(address indexed updater);
    event UpdaterRemoved(address indexed updater);

    /*//////////////////////////////////////////////////////////////
                                 TYPES
    //////////////////////////////////////////////////////////////*/

    /// @dev Packed into single 256-bit slot: score(64) + lastUpdated(64) + flags(8) = 136 bits
    struct RiskData {
        uint64 score;       // 0-100
        uint64 lastUpdated; // Unix timestamp
        uint8 flags;        // Bit 0: isTracked
    }

    /*//////////////////////////////////////////////////////////////
                                 STATE
    //////////////////////////////////////////////////////////////*/

    mapping(bytes32 => RiskData) internal _data;
    mapping(bytes32 => string) public protocolNames;
    bytes32[] public protocolIds;
    uint64 public alertThreshold = 70;
    mapping(address => bool) public authorizedUpdaters;

    /*//////////////////////////////////////////////////////////////
                              CONSTRUCTOR
    //////////////////////////////////////////////////////////////*/

    constructor() Ownable(msg.sender) {
        authorizedUpdaters[msg.sender] = true;
        emit UpdaterAdded(msg.sender);
    }

    /*//////////////////////////////////////////////////////////////
                               MODIFIERS
    //////////////////////////////////////////////////////////////*/

    modifier onlyAuthorized() {
        if (!authorizedUpdaters[msg.sender] && msg.sender != owner()) revert Unauthorized();
        _;
    }

    /*//////////////////////////////////////////////////////////////
                            WRITE FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Update single protocol risk score
    function updateRiskScore(bytes32 id, uint64 score) external onlyAuthorized {
        _update(id, score);
    }

    /// @notice Update by name (auto-hashes and stores name)
    function updateRiskScoreByName(string calldata name, uint64 score) external onlyAuthorized {
        bytes32 id = keccak256(bytes(name));
        if (bytes(protocolNames[id]).length == 0) protocolNames[id] = name;
        _update(id, score);
    }

    /// @notice Batch update - saves ~21k gas base + ~2k per protocol
    function batchUpdateRiskScores(
        bytes32[] calldata ids,
        uint64[] calldata scores
    ) external onlyAuthorized {
        uint256 len = ids.length;
        if (len == 0) revert EmptyArray();
        if (len != scores.length) revert ArrayLengthMismatch();

        for (uint256 i; i < len;) {
            _update(ids[i], scores[i]);
            unchecked { ++i; }
        }
    }

    /// @notice Batch update by names
    function batchUpdateRiskScoresByName(
        string[] calldata names,
        uint64[] calldata scores
    ) external onlyAuthorized {
        uint256 len = names.length;
        if (len == 0) revert EmptyArray();
        if (len != scores.length) revert ArrayLengthMismatch();

        for (uint256 i; i < len;) {
            bytes32 id = keccak256(bytes(names[i]));
            if (bytes(protocolNames[id]).length == 0) protocolNames[id] = names[i];
            _update(id, scores[i]);
            unchecked { ++i; }
        }
    }

    /*//////////////////////////////////////////////////////////////
                            VIEW FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Get risk score with staleness check
    function getRiskScore(bytes32 id) external view returns (uint64, uint64, bool) {
        RiskData storage d = _data[id];
        return (d.score, d.lastUpdated, block.timestamp > d.lastUpdated + _STALENESS);
    }

    /// @notice Get risk score by protocol name
    function getRiskScoreByName(string calldata name) external view returns (uint64, uint64, bool) {
        RiskData storage d = _data[keccak256(bytes(name))];
        return (d.score, d.lastUpdated, block.timestamp > d.lastUpdated + _STALENESS);
    }

    /// @notice Check if any protocol exceeds alert threshold
    function isAnyProtocolHighRisk() external view returns (bool) {
        uint256 len = protocolIds.length;
        uint64 t = alertThreshold;
        for (uint256 i; i < len;) {
            if (_data[protocolIds[i]].score >= t) return true;
            unchecked { ++i; }
        }
        return false;
    }

    /// @notice Get all protocols above alert threshold
    function getHighRiskProtocols() external view returns (bytes32[] memory result) {
        uint256 len = protocolIds.length;
        uint64 t = alertThreshold;

        // Count first
        uint256 count;
        for (uint256 i; i < len;) {
            if (_data[protocolIds[i]].score >= t) {
                unchecked { ++count; }
            }
            unchecked { ++i; }
        }

        // Populate
        result = new bytes32[](count);
        uint256 idx;
        for (uint256 i; i < len;) {
            bytes32 id = protocolIds[i];
            if (_data[id].score >= t) {
                result[idx] = id;
                unchecked { ++idx; }
            }
            unchecked { ++i; }
        }
    }

    /// @notice Total tracked protocols
    function getProtocolCount() external view returns (uint256) {
        return protocolIds.length;
    }

    /// @notice Check if protocol is tracked
    function isTracked(bytes32 id) external view returns (bool) {
        return _data[id].flags & 1 == 1;
    }

    /// @notice Convert name to bytes32 ID
    function toProtocolId(string memory name) public pure returns (bytes32) {
        return keccak256(bytes(name));
    }

    /// @notice Get staleness period
    function STALENESS_PERIOD() external pure returns (uint64) {
        return _STALENESS;
    }

    /// @notice Get max score
    function MAX_SCORE() external pure returns (uint64) {
        return _MAX_SCORE;
    }

    /*//////////////////////////////////////////////////////////////
                            ADMIN FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function addAuthorizedUpdater(address updater) external onlyOwner {
        authorizedUpdaters[updater] = true;
        emit UpdaterAdded(updater);
    }

    function removeAuthorizedUpdater(address updater) external onlyOwner {
        authorizedUpdaters[updater] = false;
        emit UpdaterRemoved(updater);
    }

    function setAlertThreshold(uint64 threshold) external onlyOwner {
        if (threshold > _MAX_SCORE) revert InvalidThreshold();
        emit ThresholdUpdated(alertThreshold, threshold);
        alertThreshold = threshold;
    }

    /*//////////////////////////////////////////////////////////////
                           INTERNAL FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function _update(bytes32 id, uint64 score) private {
        if (score > _MAX_SCORE) revert InvalidScore();

        RiskData storage d = _data[id];
        uint64 old = d.score;
        uint64 ts = uint64(block.timestamp);

        d.score = score;
        d.lastUpdated = ts;

        // Track new protocol
        if (d.flags & 1 == 0) {
            d.flags = 1;
            protocolIds.push(id);
        }

        emit RiskScoreUpdated(id, old, score, ts);
        if (score >= alertThreshold) emit HighRiskAlert(id, score, ts);
    }
}
