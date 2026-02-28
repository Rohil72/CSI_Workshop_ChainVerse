// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

// =============================================================
//   REFUGEE ALLOWANCE CENTER — BLOCKCHAIN AUDIT SYSTEM
//   Deployed & tested on: Remix IDE + Sepolia Testnet
//
//   ROLES:
//     Owner   → Adds/removes Managers
//     Manager → Registers and removes Beneficiaries (Refugees)
//     Benefactor → Donates ETH to the pool
//     Beneficiary → Receives and withdraws their share
//
//   AUDIT:
//     Every action emits an Event visible on Etherscan
// =============================================================

contract AllowanceCenter {

    // ─────────────────────────────────────────────────────────────
    //  STATE VARIABLES
    // ─────────────────────────────────────────────────────────────

    address public owner; // Deployer of the contract

    // Mappings store true/false per address
    mapping(address => bool) public isManager;
    mapping(address => bool) public isBeneficiary;

    // Tracks how much ETH each beneficiary can withdraw
    mapping(address => uint256) public pendingBalance;

    // Tracks lifetime stats per address
    mapping(address => uint256) public totalReceivedByBeneficiary;
    mapping(address => uint256) public totalDonatedByBenefactor;

    // Dynamic lists
    address[] public beneficiaryList;
    address[] public managerList;

    // Global counters (in Wei: 1 ETH = 1e18 Wei)
    uint256 public totalDonated;
    uint256 public totalDistributed;
    uint256 public totalWithdrawn;

    // Pause switch — owner can freeze the contract in emergencies
    bool public paused = false;

    // ─────────────────────────────────────────────────────────────
    //  EVENTS  (These appear on Sepolia Etherscan as audit logs)
    // ─────────────────────────────────────────────────────────────

    event ManagerAdded(address indexed manager, address indexed addedBy, uint256 timestamp);
    event ManagerRemoved(address indexed manager, address indexed removedBy, uint256 timestamp);

    event BeneficiaryRegistered(address indexed refugee, address indexed registeredBy, uint256 timestamp);
    event BeneficiaryRemoved(address indexed refugee, address indexed removedBy, uint256 timestamp);

    event DonationReceived(address indexed benefactor, uint256 amountWei, uint256 beneficiaryCount, uint256 timestamp);
    event FundsDistributed(uint256 totalWei, uint256 sharePerBeneficiary, uint256 beneficiaryCount, uint256 timestamp);

    event Withdrawal(address indexed refugee, uint256 amountWei, uint256 timestamp);
    event ContractPaused(address indexed by, uint256 timestamp);
    event ContractUnpaused(address indexed by, uint256 timestamp);
    event EmergencyWithdraw(address indexed to, uint256 amountWei, uint256 timestamp);

    // ─────────────────────────────────────────────────────────────
    //  MODIFIERS (Reusable access control checks)
    // ─────────────────────────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "ERROR: Only owner can do this");
        _;
    }

    modifier onlyManager() {
        require(isManager[msg.sender], "ERROR: Only managers can do this");
        _;
    }

    modifier notPaused() {
        require(!paused, "ERROR: Contract is paused");
        _;
    }

    // ─────────────────────────────────────────────────────────────
    //  CONSTRUCTOR — runs once when contract is deployed
    // ─────────────────────────────────────────────────────────────

    constructor() {
        owner = msg.sender;
        // Deployer is automatically a manager too
        isManager[msg.sender] = true;
        managerList.push(msg.sender);
        emit ManagerAdded(msg.sender, msg.sender, block.timestamp);
    }

    // ─────────────────────────────────────────────────────────────
    //  OWNER FUNCTIONS
    // ─────────────────────────────────────────────────────────────

    /// @notice Add a new manager (e.g. an NGO staff member)
    function addManager(address _manager) external onlyOwner {
        require(_manager != address(0), "ERROR: Zero address");
        require(!isManager[_manager], "ERROR: Already a manager");

        isManager[_manager] = true;
        managerList.push(_manager);

        emit ManagerAdded(_manager, msg.sender, block.timestamp);
    }

    /// @notice Remove an existing manager
    function removeManager(address _manager) external onlyOwner {
        require(_manager != owner, "ERROR: Cannot remove owner");
        require(isManager[_manager], "ERROR: Not a manager");

        isManager[_manager] = false;
        _removeFromList(managerList, _manager);

        emit ManagerRemoved(_manager, msg.sender, block.timestamp);
    }

    /// @notice Pause the contract in case of emergency
    function pause() external onlyOwner {
        paused = true;
        emit ContractPaused(msg.sender, block.timestamp);
    }

    /// @notice Unpause the contract
    function unpause() external onlyOwner {
        paused = false;
        emit ContractUnpaused(msg.sender, block.timestamp);
    }

    /// @notice Emergency: withdraw all ETH to owner (last resort)
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "ERROR: Nothing to withdraw");

        (bool success, ) = payable(owner).call{value: balance}("");
        require(success, "ERROR: Transfer failed");

        emit EmergencyWithdraw(owner, balance, block.timestamp);
    }

    // ─────────────────────────────────────────────────────────────
    //  MANAGER FUNCTIONS
    // ─────────────────────────────────────────────────────────────

    /// @notice Register a refugee as a beneficiary
    function registerBeneficiary(address _refugee) external onlyManager notPaused {
        require(_refugee != address(0), "ERROR: Zero address");
        require(!isBeneficiary[_refugee], "ERROR: Already registered");

        isBeneficiary[_refugee] = true;
        beneficiaryList.push(_refugee);

        emit BeneficiaryRegistered(_refugee, msg.sender, block.timestamp);
    }

    /// @notice Remove a refugee from the beneficiary list
    function removeBeneficiary(address _refugee) external onlyManager {
        require(isBeneficiary[_refugee], "ERROR: Not registered");

        isBeneficiary[_refugee] = false;
        _removeFromList(beneficiaryList, _refugee);

        emit BeneficiaryRemoved(_refugee, msg.sender, block.timestamp);
    }

    // ─────────────────────────────────────────────────────────────
    //  DONATION — Anyone can send ETH here
    // ─────────────────────────────────────────────────────────────

    /// @notice Donate ETH. It auto-distributes equally among all beneficiaries.
    /// @dev Send ETH directly to this function via Remix "Value" field
    function donate() external payable notPaused {
        require(msg.value > 0, "ERROR: Must send ETH > 0");
        require(beneficiaryList.length > 0, "ERROR: No beneficiaries registered yet");

        totalDonated += msg.value;
        totalDonatedByBenefactor[msg.sender] += msg.value;

        emit DonationReceived(msg.sender, msg.value, beneficiaryList.length, block.timestamp);

        // Distribute immediately
        _distribute(msg.value);
    }

    /// @notice Fallback — if someone sends ETH directly to the contract address
    receive() external payable {
        require(msg.value > 0, "ERROR: Must send ETH > 0");
        require(!paused, "ERROR: Contract is paused");
        require(beneficiaryList.length > 0, "ERROR: No beneficiaries registered yet");

        totalDonated += msg.value;
        totalDonatedByBenefactor[msg.sender] += msg.value;
        emit DonationReceived(msg.sender, msg.value, beneficiaryList.length, block.timestamp);
        _distribute(msg.value);
    }

    // ─────────────────────────────────────────────────────────────
    //  INTERNAL: Equal Distribution Logic
    // ─────────────────────────────────────────────────────────────

    function _distribute(uint256 _totalWei) internal {
        uint256 count = beneficiaryList.length;

        // Integer division — each gets equal share
        uint256 sharePerBeneficiary = _totalWei / count;

        // Dust (remainder from division) stays in contract
        // e.g. 10 Wei / 3 beneficiaries = 3 Wei each, 1 Wei stays

        for (uint256 i = 0; i < count; i++) {
            address refugee = beneficiaryList[i];
            pendingBalance[refugee] += sharePerBeneficiary;
            totalReceivedByBeneficiary[refugee] += sharePerBeneficiary;
        }

        totalDistributed += sharePerBeneficiary * count;

        emit FundsDistributed(_totalWei, sharePerBeneficiary, count, block.timestamp);
    }

    // ─────────────────────────────────────────────────────────────
    //  BENEFICIARY: Withdraw their allocated allowance
    // ─────────────────────────────────────────────────────────────

    /// @notice Refugee calls this to receive their ETH allowance
    function withdraw() external notPaused {
        uint256 amount = pendingBalance[msg.sender];
        require(
            isBeneficiary[msg.sender] || amount > 0,
            "ERROR: You are not a registered beneficiary"
        );
        require(amount > 0, "ERROR: No balance to withdraw");

        // Zero out BEFORE transfer (prevents re-entrancy attacks)
        pendingBalance[msg.sender] = 0;
        totalWithdrawn += amount;

        (bool success, ) = payable(msg.sender).call{value: amount}("");
        require(success, "ERROR: ETH transfer failed");

        emit Withdrawal(msg.sender, amount, block.timestamp);
    }

    // ─────────────────────────────────────────────────────────────
    //  VIEW FUNCTIONS (Read-only, no gas when called externally)
    // ─────────────────────────────────────────────────────────────

    /// @notice Get list of all registered beneficiaries
    function getBeneficiaries() external view returns (address[] memory) {
        return beneficiaryList;
    }

    /// @notice Get list of all managers
    function getManagers() external view returns (address[] memory) {
        return managerList;
    }

    /// @notice How many beneficiaries are registered?
    function getBeneficiaryCount() external view returns (uint256) {
        return beneficiaryList.length;
    }

    /// @notice How much ETH is currently sitting in the contract?
    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /// @notice Get a full audit summary in one call
    function getAuditSummary() external view returns (
        uint256 _totalDonated,
        uint256 _totalDistributed,
        uint256 _totalWithdrawn,
        uint256 _contractBalance,
        uint256 _beneficiaryCount,
        uint256 _managerCount,
        bool    _isPaused
    ) {
        return (
            totalDonated,
            totalDistributed,
            totalWithdrawn,
            address(this).balance,
            beneficiaryList.length,
            managerList.length,
            paused
        );
    }

    /// @notice Check if an address would receive X Wei per donation of Y Wei
    function simulateDistribution(uint256 donationWei) external view returns (uint256 sharePerBeneficiary) {
        require(beneficiaryList.length > 0, "No beneficiaries");
        return donationWei / beneficiaryList.length;
    }

    // ─────────────────────────────────────────────────────────────
    //  INTERNAL HELPER: Remove address from a dynamic array
    // ─────────────────────────────────────────────────────────────

    function _removeFromList(address[] storage list, address target) internal {
        for (uint256 i = 0; i < list.length; i++) {
            if (list[i] == target) {
                // Swap with last element, then pop
                list[i] = list[list.length - 1];
                list.pop();
                break;
            }
        }
    }
}
