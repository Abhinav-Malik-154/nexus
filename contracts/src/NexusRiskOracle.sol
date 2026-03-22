// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title NexusRiskOracle
 * @notice Stores AI-generated risk scores on-chain
 * @dev Updated by Nexus backend every 15 minutes
 * 
 * This is the bridge between off-chain AI
 * and on-chain protection contracts.
 * 
 * Flow:
 * Python GNN generates risk scores
 * → Backend calls updateRiskScore()
 * → ProtectionVault reads scores
 * → Auto-protection triggers if threshold hit
 */
contract NexusRiskOracle is Ownable {

    // Risk score for each protocol
    // Score: 0-100 (100 = maximum danger)
    mapping(string => uint256) public riskScores;
    
    // When each score was last updated
    mapping(string => uint256) public lastUpdated;
    
    // All tracked protocols
    string[] public protocols;
    mapping(string => bool) public isTracked;
    
    // Alert threshold — default 70/100
    uint256 public alertThreshold = 70;
    
    // Authorized updaters (our backend)
    mapping(address => bool) public authorizedUpdaters;

    // Events
    event RiskScoreUpdated(
        string indexed protocol,
        uint256 oldScore,
        uint256 newScore,
        uint256 timestamp
    );
    
    event HighRiskAlert(
        string indexed protocol,
        uint256 riskScore,
        uint256 timestamp
    );
    
    event ThresholdUpdated(
        uint256 oldThreshold,
        uint256 newThreshold
    );

    constructor() Ownable(msg.sender) {
        authorizedUpdaters[msg.sender] = true;
    }

    modifier onlyAuthorized() {
        require(
            authorizedUpdaters[msg.sender] || 
            msg.sender == owner(),
            "Not authorized to update scores"
        );
        _;
    }

    /**
     * @notice Update risk score for a protocol
     * @param protocol Protocol name (e.g. "Aave V3")
     * @param score Risk score 0-100
     */
    function updateRiskScore(
        string calldata protocol,
        uint256 score
    ) external onlyAuthorized {
        require(score <= 100, "Score must be 0-100");
        
        uint256 oldScore = riskScores[protocol];
        riskScores[protocol] = score;
        lastUpdated[protocol] = block.timestamp;
        
        // Add to tracked list if new
        if (!isTracked[protocol]) {
            protocols.push(protocol);
            isTracked[protocol] = true;
        }
        
        emit RiskScoreUpdated(
            protocol,
            oldScore,
            score,
            block.timestamp
        );
        
        // Emit alert if high risk
        if (score >= alertThreshold) {
            emit HighRiskAlert(
                protocol,
                score,
                block.timestamp
            );
        }
    }

    /**
     * @notice Batch update multiple protocols at once
     * @dev Saves gas vs individual updates
     */
    function batchUpdateRiskScores(
        string[] calldata _protocols,
        uint256[] calldata scores
    ) external onlyAuthorized {
        require(
            _protocols.length == scores.length,
            "Arrays must be same length"
        );
        
        for (uint256 i = 0; i < _protocols.length; i++) {
            require(scores[i] <= 100, "Score must be 0-100");
            
            uint256 oldScore = riskScores[_protocols[i]];
            riskScores[_protocols[i]] = scores[i];
            lastUpdated[_protocols[i]] = block.timestamp;
            
            if (!isTracked[_protocols[i]]) {
                protocols.push(_protocols[i]);
                isTracked[_protocols[i]] = true;
            }
            
            emit RiskScoreUpdated(
                _protocols[i],
                oldScore,
                scores[i],
                block.timestamp
            );
            
            if (scores[i] >= alertThreshold) {
                emit HighRiskAlert(
                    _protocols[i],
                    scores[i],
                    block.timestamp
                );
            }
        }
    }

    /**
     * @notice Get risk score for a protocol
     * @return score Current risk score 0-100
     * @return updated When score was last updated
     * @return isStale True if not updated in 1 hour
     */
    function getRiskScore(string calldata protocol)
        external
        view
        returns (
            uint256 score,
            uint256 updated,
            bool isStale
        )
    {
        score = riskScores[protocol];
        updated = lastUpdated[protocol];
        isStale = block.timestamp - updated > 1 hours;
    }

    /**
     * @notice Check if any protocol is above threshold
     * @return true if any protocol is high risk
     */
    function isAnyProtocolHighRisk()
        external
        view
        returns (bool)
    {
        for (uint256 i = 0; i < protocols.length; i++) {
            if (riskScores[protocols[i]] >= alertThreshold) {
                return true;
            }
        }
        return false;
    }

    /**
     * @notice Get all protocols above threshold
     */
    function getHighRiskProtocols()
        external
        view
        returns (string[] memory highRisk)
    {
        uint256 count = 0;
        for (uint256 i = 0; i < protocols.length; i++) {
            if (riskScores[protocols[i]] >= alertThreshold) {
                count++;
            }
        }
        
        highRisk = new string[](count);
        uint256 idx = 0;
        for (uint256 i = 0; i < protocols.length; i++) {
            if (riskScores[protocols[i]] >= alertThreshold) {
                highRisk[idx] = protocols[i];
                idx++;
            }
        }
    }

    function addAuthorizedUpdater(address updater) 
        external onlyOwner {
        authorizedUpdaters[updater] = true;
    }

    function setAlertThreshold(uint256 threshold)
        external onlyOwner {
        require(threshold <= 100, "Invalid threshold");
        uint256 old = alertThreshold;
        alertThreshold = threshold;
        emit ThresholdUpdated(old, threshold);
    }

    function getProtocolCount() 
        external view returns (uint256) {
        return protocols.length;
    }
}