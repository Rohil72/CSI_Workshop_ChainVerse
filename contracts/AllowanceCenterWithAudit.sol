// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

// =============================================================
//   ALLOWANCE CENTER + AUDIT INTEGRATION
//
//   This is the FULL SYSTEM in one file:
//   - AllowanceCenter logic
//   - AuditLogger built-in
//
//   DEPLOY THIS FILE on Remix for the complete experience.
//   (No need to deploy separate contracts)
//
//   HOW TO USE IN REMIX:
//   1. Paste this file into a new .sol file
//   2. Compile with Solidity 0.8.19
//   3. Deploy "AllowanceCenterWithAudit"
//   4. Use the deployed contract's functions from Remix UI
// =============================================================

// ──────────────────────────────────────────────────────────────
//  EMBEDDED AUDIT LOGGER (no imports needed)
// ──────────────────────────────────────────────────────────────

contract AuditLogger {

    enum ActionType {
        MANAGER_ADDED,
        MANAGER_REMOVED,
        BENEFICIARY_REGISTERED,
        BENEFICIARY_REMOVED,
        DONATION_RECEIVED,
        FUNDS_DISTRIBUTED,
        WITHDRAWAL,
        CONTRACT_PAUSED,
        CONTRACT_UNPAUSED
    }

    struct AuditRecord {
        uint256    id;
        ActionType action;
        address    actor;
        address    target;
        uint256    amountWei;
        string     note;
        uint256    timestamp;
        uint256    blockNumber;
    }

    AuditRecord[] private auditLog;
    uint256 public recordCount;

    address public authorizedWriter; // Only AllowanceCenterWithAudit

    event AuditRecordCreated(uint256 indexed id, ActionType indexed action, address indexed actor, uint256 timestamp);

    constructor(address _writer) {
        authorizedWriter = _writer;
    }

    modifier onlyWriter() {
        require(msg.sender == authorizedWriter, "Not authorized");
        _;
    }

    // Write functions
    function log(ActionType _action, address _actor, address _target, uint256 _amount, string calldata _note)
        external onlyWriter
    {
        uint256 id = recordCount++;
        auditLog.push(AuditRecord(id, _action, _actor, _target, _amount, _note, block.timestamp, block.number));
        emit AuditRecordCreated(id, _action, _actor, block.timestamp);
    }

    // Read functions
    function getRecord(uint256 id) external view returns (AuditRecord memory) {
        require(id < recordCount, "Not found");
        return auditLog[id];
    }

    function getAllRecords() external view returns (AuditRecord[] memory) {
        return auditLog;
    }

    function getRecordsByAddress(address addr) external view returns (AuditRecord[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < auditLog.length; i++)
            if (auditLog[i].actor == addr || auditLog[i].target == addr) count++;

        AuditRecord[] memory res = new AuditRecord[](count);
        uint256 idx = 0;
        for (uint256 i = 0; i < auditLog.length; i++)
            if (auditLog[i].actor == addr || auditLog[i].target == addr)
                res[idx++] = auditLog[i];

        return res;
    }

    function getLatestN(uint256 n) external view returns (AuditRecord[] memory) {
        uint256 total = auditLog.length;
        if (n > total) n = total;
        AuditRecord[] memory res = new AuditRecord[](n);
        for (uint256 i = 0; i < n; i++)
            res[i] = auditLog[total - n + i];
        return res;
    }
}


// ──────────────────────────────────────────────────────────────
//  MAIN CONTRACT
// ──────────────────────────────────────────────────────────────

contract AllowanceCenterWithAudit {

    // ─── State ─────────────────────────────────────────────────
    address public owner;
    AuditLogger public logger; // The audit sub-contract

    mapping(address => bool)    public isManager;
    mapping(address => bool)    public isBeneficiary;
    mapping(address => uint256) public pendingBalance;
    mapping(address => uint256) public lifetimeReceived;
    mapping(address => uint256) public lifetimeDonated;

    address[] public beneficiaryList;
    address[] public managerList;

    uint256 public totalDonated;
    uint256 public totalDistributed;
    uint256 public totalWithdrawn;
    bool    public paused;

    // ─── Events ────────────────────────────────────────────────
    event ManagerAdded(address indexed manager);
    event ManagerRemoved(address indexed manager);
    event BeneficiaryRegistered(address indexed refugee);
    event BeneficiaryRemoved(address indexed refugee);
    event DonationReceived(address indexed from, uint256 amountWei, uint256 numBeneficiaries);
    event FundsDistributed(uint256 totalWei, uint256 shareWei, uint256 numBeneficiaries);
    event Withdrawal(address indexed refugee, uint256 amountWei);
    event Paused();
    event Unpaused();

    // ─── Modifiers ─────────────────────────────────────────────
    modifier onlyOwner()  { require(msg.sender == owner,           "Only owner");   _; }
    modifier onlyManager(){ require(isManager[msg.sender],         "Only manager"); _; }
    modifier notPaused()  { require(!paused,                       "Paused");       _; }

    // ─── Constructor ───────────────────────────────────────────
    constructor() {
        owner = msg.sender;

        // Deploy the AuditLogger child contract, giving this contract write access
        logger = new AuditLogger(address(this));

        isManager[msg.sender] = true;
        managerList.push(msg.sender);

        logger.log(
            AuditLogger.ActionType.MANAGER_ADDED,
            msg.sender, msg.sender, 0,
            "Contract deployed, owner set as first manager"
        );
    }

    // ─── Owner: Manage Managers ─────────────────────────────────

    function addManager(address _m) external onlyOwner {
        require(_m != address(0) && !isManager[_m], "Invalid or duplicate");
        isManager[_m] = true;
        managerList.push(_m);
        emit ManagerAdded(_m);
        logger.log(AuditLogger.ActionType.MANAGER_ADDED, msg.sender, _m, 0, "Manager added by owner");
    }

    function removeManager(address _m) external onlyOwner {
        require(_m != owner && isManager[_m], "Cannot remove owner / not manager");
        isManager[_m] = false;
        _removeFromArray(managerList, _m);
        emit ManagerRemoved(_m);
        logger.log(AuditLogger.ActionType.MANAGER_REMOVED, msg.sender, _m, 0, "Manager removed by owner");
    }

    function pause() external onlyOwner {
        paused = true;
        emit Paused();
        logger.log(AuditLogger.ActionType.CONTRACT_PAUSED, msg.sender, address(0), 0, "Contract paused");
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused();
        logger.log(AuditLogger.ActionType.CONTRACT_UNPAUSED, msg.sender, address(0), 0, "Contract unpaused");
    }

    function emergencyWithdraw() external onlyOwner {
        uint256 bal = address(this).balance;
        require(bal > 0, "Nothing to withdraw");
        (bool ok,) = payable(owner).call{value: bal}("");
        require(ok, "Transfer failed");
    }

    // ─── Manager: Manage Beneficiaries ─────────────────────────

    function registerBeneficiary(address _r) external onlyManager notPaused {
        require(_r != address(0) && !isBeneficiary[_r], "Invalid or already registered");
        isBeneficiary[_r] = true;
        beneficiaryList.push(_r);
        emit BeneficiaryRegistered(_r);
        logger.log(AuditLogger.ActionType.BENEFICIARY_REGISTERED, msg.sender, _r, 0, "Beneficiary registered");
    }

    function removeBeneficiary(address _r) external onlyManager {
        require(isBeneficiary[_r], "Not registered");
        isBeneficiary[_r] = false;
        _removeFromArray(beneficiaryList, _r);
        emit BeneficiaryRemoved(_r);
        logger.log(AuditLogger.ActionType.BENEFICIARY_REMOVED, msg.sender, _r, 0, "Beneficiary removed");
    }

    // ─── Donate ────────────────────────────────────────────────

    /// @notice Send ETH here to donate. Set value in Remix "Value" field.
    function donate() external payable notPaused {
        require(msg.value > 0, "Send ETH > 0");
        require(beneficiaryList.length > 0, "No beneficiaries yet");

        totalDonated               += msg.value;
        lifetimeDonated[msg.sender]+= msg.value;

        emit DonationReceived(msg.sender, msg.value, beneficiaryList.length);
        logger.log(AuditLogger.ActionType.DONATION_RECEIVED, msg.sender, address(0), msg.value, "Donation received");

        _distribute(msg.value);
    }

    receive() external payable {
        if (msg.value > 0 && beneficiaryList.length > 0 && !paused) {
            totalDonated               += msg.value;
            lifetimeDonated[msg.sender]+= msg.value;
            emit DonationReceived(msg.sender, msg.value, beneficiaryList.length);
            logger.log(AuditLogger.ActionType.DONATION_RECEIVED, msg.sender, address(0), msg.value, "Direct ETH donation");
            _distribute(msg.value);
        }
    }

    // ─── Internal: Distribute Equally ──────────────────────────

    function _distribute(uint256 total) internal {
        uint256 n     = beneficiaryList.length;
        uint256 share = total / n; // Integer division = equal share

        for (uint256 i = 0; i < n; i++) {
            pendingBalance[beneficiaryList[i]]   += share;
            lifetimeReceived[beneficiaryList[i]] += share;
        }

        uint256 distributed = share * n;
        totalDistributed += distributed;

        emit FundsDistributed(total, share, n);
        logger.log(AuditLogger.ActionType.FUNDS_DISTRIBUTED, address(this), address(0), distributed,
            "Funds distributed equally");
    }

    // ─── Beneficiary: Withdraw ──────────────────────────────────

    /// @notice Refugees call this to receive their allowance
    function withdraw() external notPaused {
        require(isBeneficiary[msg.sender], "Not a beneficiary");
        uint256 amt = pendingBalance[msg.sender];
        require(amt > 0, "No balance");

        pendingBalance[msg.sender] = 0; // Zero before transfer (re-entrancy guard)
        totalWithdrawn += amt;

        (bool ok,) = payable(msg.sender).call{value: amt}("");
        require(ok, "Transfer failed");

        emit Withdrawal(msg.sender, amt);
        logger.log(AuditLogger.ActionType.WITHDRAWAL, msg.sender, msg.sender, amt, "Beneficiary withdrawal");
    }

    // ─── View / Read Functions ──────────────────────────────────

    function getBeneficiaries()   external view returns (address[] memory) { return beneficiaryList; }
    function getManagers()        external view returns (address[] memory) { return managerList; }
    function getBeneficiaryCount()external view returns (uint256) { return beneficiaryList.length; }
    function getContractBalance() external view returns (uint256) { return address(this).balance; }
    function getLoggerAddress()   external view returns (address) { return address(logger); }

    /// @notice Full audit snapshot
    function getAuditSummary() external view returns (
        uint256 donated, uint256 distributed, uint256 withdrawn,
        uint256 contractBal, uint256 beneficiaries, uint256 managers,
        bool isPaused, uint256 auditRecords
    ) {
        return (
            totalDonated, totalDistributed, totalWithdrawn,
            address(this).balance, beneficiaryList.length, managerList.length,
            paused, logger.recordCount()
        );
    }

    /// @notice Preview — how much would each beneficiary get if X Wei donated?
    function previewDistribution(uint256 weiAmount) external view returns (uint256 sharePerPerson) {
        require(beneficiaryList.length > 0, "No beneficiaries");
        return weiAmount / beneficiaryList.length;
    }

    // ─── Internal Helper ───────────────────────────────────────

    function _removeFromArray(address[] storage arr, address target) internal {
        for (uint256 i = 0; i < arr.length; i++) {
            if (arr[i] == target) {
                arr[i] = arr[arr.length - 1];
                arr.pop();
                return;
            }
        }
    }
}
