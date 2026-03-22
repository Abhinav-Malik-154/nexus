// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "./NexusRiskOracle.sol";

/**
 * @title ProtectionVault
 * @notice Automatically protects user funds when
 *         AI-detected risk crosses threshold
 * 
 * How it works:
 * 1. User deposits tokens + sets rules:
 *    "If Aave V3 risk > 70 → withdraw all"
 * 2. Chainlink Automation (or anyone) calls
 *    checkAndProtect() every block
 * 3. If rule triggers → funds auto-withdrawn
 *    to user's safe address
 * 4. User gets notification. Funds are safe.
 */
contract ProtectionVault is ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    NexusRiskOracle public immutable oracle;

    struct ProtectionRule {
        string protocol;      // Protocol to watch
        uint256 riskThreshold; // Trigger if risk >= this
        address token;         // Token to protect
        address safeAddress;   // Where to send funds
        bool isActive;         // Is rule active
        uint256 createdAt;     // When rule was created
    }

    struct UserVault {
        mapping(address => uint256) balances;
        ProtectionRule[] rules;
        bool exists;
    }

    // User address → vault
    mapping(address => UserVault) private vaults;
    
    // All users for iteration
    address[] public users;

    // Events
    event Deposited(
        address indexed user,
        address indexed token,
        uint256 amount
    );
    
    event Withdrawn(
        address indexed user,
        address indexed token,
        uint256 amount,
        address destination
    );
    
    event ProtectionTriggered(
        address indexed user,
        string protocol,
        uint256 riskScore,
        address token,
        uint256 amount,
        address safeAddress
    );
    
    event RuleAdded(
        address indexed user,
        string protocol,
        uint256 threshold
    );

    constructor(address _oracle) Ownable(msg.sender) {
        oracle = NexusRiskOracle(_oracle);
    }

    /**
     * @notice Deposit tokens into protection vault
     * @param token Token address to deposit
     * @param amount Amount to deposit
     */
    function deposit(
        address token,
        uint256 amount
    ) external nonReentrant {
        require(amount > 0, "Amount must be > 0");
        
        IERC20(token).safeTransferFrom(
            msg.sender,
            address(this),
            amount
        );
        
        if (!vaults[msg.sender].exists) {
            users.push(msg.sender);
            vaults[msg.sender].exists = true;
        }
        
        vaults[msg.sender].balances[token] += amount;
        
        emit Deposited(msg.sender, token, amount);
    }

    /**
     * @notice Add a protection rule
     * @param protocol Protocol name to watch
     * @param riskThreshold Trigger if risk >= this (0-100)
     * @param token Token to protect
     * @param safeAddress Where to send funds if triggered
     */
    function addProtectionRule(
        string calldata protocol,
        uint256 riskThreshold,
        address token,
        address safeAddress
    ) external {
        require(riskThreshold <= 100, "Invalid threshold");
        require(safeAddress != address(0), "Invalid address");
        require(
            vaults[msg.sender].exists,
            "Deposit first"
        );

        vaults[msg.sender].rules.push(ProtectionRule({
            protocol: protocol,
            riskThreshold: riskThreshold,
            token: token,
            safeAddress: safeAddress,
            isActive: true,
            createdAt: block.timestamp
        }));

        emit RuleAdded(
            msg.sender,
            protocol,
            riskThreshold
        );
    }

    /**
     * @notice Check and execute protection for a user
     * @dev Called by Chainlink Automation or anyone
     * @param user Address to check protection for
     */
    function checkAndProtect(
        address user
    ) external nonReentrant {
        require(
            vaults[user].exists,
            "No vault found"
        );

        UserVault storage vault = vaults[user];

        for (uint256 i = 0; i < vault.rules.length; i++) {
            ProtectionRule storage rule = vault.rules[i];
            
            if (!rule.isActive) continue;

            // Check current risk from oracle
            (uint256 currentRisk, , bool isStale) = 
                oracle.getRiskScore(rule.protocol);

            // Skip stale data
            if (isStale) continue;

            // Trigger protection if risk threshold hit
            if (currentRisk >= rule.riskThreshold) {
                uint256 balance = vault.balances[rule.token];
                
                if (balance > 0) {
                    // Transfer to safe address
                    vault.balances[rule.token] = 0;
                    rule.isActive = false;
                    
                    IERC20(rule.token).safeTransfer(
                        rule.safeAddress,
                        balance
                    );

                    emit ProtectionTriggered(
                        user,
                        rule.protocol,
                        currentRisk,
                        rule.token,
                        balance,
                        rule.safeAddress
                    );
                }
            }
        }
    }

    /**
     * @notice Manual withdrawal
     * @param token Token to withdraw
     * @param amount Amount to withdraw
     */
    function withdraw(
        address token,
        uint256 amount
    ) external nonReentrant {
        require(
            vaults[msg.sender].balances[token] >= amount,
            "Insufficient balance"
        );
        
        vaults[msg.sender].balances[token] -= amount;
        
        IERC20(token).safeTransfer(msg.sender, amount);
        
        emit Withdrawn(
            msg.sender,
            token,
            amount,
            msg.sender
        );
    }

    /**
     * @notice Get user balance for a token
     */
    function getBalance(
        address user,
        address token
    ) external view returns (uint256) {
        return vaults[user].balances[token];
    }

    /**
     * @notice Get user's protection rules
     */
    function getRules(address user)
        external
        view
        returns (ProtectionRule[] memory)
    {
        return vaults[user].rules;
    }

    /**
     * @notice Get total users in vault
     */
    function getTotalUsers() 
        external view returns (uint256) {
        return users.length;
    }
}