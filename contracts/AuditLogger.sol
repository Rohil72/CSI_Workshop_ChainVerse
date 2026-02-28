// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

// =============================================================
//   AUDIT LOGGER CONTRACT
//
//   Stores a permanent, tamper-proof on-chain audit trail.
//   Linked to AllowanceCenter — the main contract calls
//   this contract's log functions to write records.
//
//   Think of this as the "ledger book" of the system.
// =============================================================

contract AuditLogger {

    // ─────────────────────────────────────────────────────────────
    //  DATA STRUCTURES
    // ─────────────────────────────────────────────────────────────

    // Types of actions we track
    enum ActionType {
        MANAGER_ADDED,          // 0
        MANAGER_REMOVED,        // 1
        BENEFICIARY_REGISTERED, // 2
        BENEFICIARY_REMOVED,    // 3
        DONATION_RECEIVED,      // 4
        FUNDS_DISTRIBUTED,      // 5
        WITHDRAWAL,             // 6
        CONTRACT_PAUSED,        // 7
        CONTRACT_UNPAUSED       // 8
    }

    // One audit record
    struct AuditRecord {
        uint256     id;          // Auto-incrementing ID
        ActionType  action;      // What happened
        address     actor;       // Who triggered it
        address     target;      // Who was affected (0x0 if N/A)
        uint256     amount;      // ETH amount in Wei (0 if N/A)
        string      note;        // Human-readable description
        uint256     timestamp;   // Block timestamp
        uint256     blockNumber; // Block number for cross-reference
    }

    // Storage
    AuditRecord[] public auditLog;
    uint256 public recordCount;

    // Only the linked AllowanceCenter can write to this log
    address public allowanceCenterAddress;
    bool    public centerLinked = false;

    // ─────────────────────────────────────────────────────────────
    //  EVENTS
    // ─────────────────────────────────────────────────────────────

    event AuditRecordCreated(
        uint256 indexed id,
        ActionType indexed action,
        address indexed actor,
        uint256 timestamp
    );

    event CenterLinked(address indexed centerAddress, uint256 timestamp);

    // ─────────────────────────────────────────────────────────────
    //  SETUP: Link to AllowanceCenter
    // ─────────────────────────────────────────────────────────────

    address public deployer;

    constructor() {
        deployer = msg.sender;
    }

    /// @notice Link this logger to the AllowanceCenter contract
    /// @dev Call this AFTER deploying AllowanceCenter, pass its address here
    function linkAllowanceCenter(address _center) external {
        require(msg.sender == deployer, "Only deployer can link");
        require(!centerLinked, "Already linked");
        require(_center != address(0), "Zero address");

        allowanceCenterAddress = _center;
        centerLinked = true;

        emit CenterLinked(_center, block.timestamp);
    }

    modifier onlyCenter() {
        require(msg.sender == allowanceCenterAddress, "Only AllowanceCenter can log");
        _;
    }

    // ─────────────────────────────────────────────────────────────
    //  LOG FUNCTIONS (called by AllowanceCenter)
    // ─────────────────────────────────────────────────────────────

    function logManagerAdded(address _manager, address _addedBy) external onlyCenter {
        _writeRecord(ActionType.MANAGER_ADDED, _addedBy, _manager, 0, "Manager added");
    }

    function logManagerRemoved(address _manager, address _removedBy) external onlyCenter {
        _writeRecord(ActionType.MANAGER_REMOVED, _removedBy, _manager, 0, "Manager removed");
    }

    function logBeneficiaryRegistered(address _refugee, address _manager) external onlyCenter {
        _writeRecord(ActionType.BENEFICIARY_REGISTERED, _manager, _refugee, 0, "Beneficiary registered");
    }

    function logBeneficiaryRemoved(address _refugee, address _manager) external onlyCenter {
        _writeRecord(ActionType.BENEFICIARY_REMOVED, _manager, _refugee, 0, "Beneficiary removed");
    }

    function logDonation(address _benefactor, uint256 _amount) external onlyCenter {
        _writeRecord(ActionType.DONATION_RECEIVED, _benefactor, address(0), _amount, "Donation received");
    }

    function logDistribution(uint256 _totalAmount, uint256 _count) external onlyCenter {
        _writeRecord(ActionType.FUNDS_DISTRIBUTED, msg.sender, address(0), _totalAmount,
            string(abi.encodePacked("Distributed to ", _uint2str(_count), " beneficiaries")));
    }

    function logWithdrawal(address _refugee, uint256 _amount) external onlyCenter {
        _writeRecord(ActionType.WITHDRAWAL, _refugee, _refugee, _amount, "Withdrawal by beneficiary");
    }

    function logPaused(address _by) external onlyCenter {
        _writeRecord(ActionType.CONTRACT_PAUSED, _by, address(0), 0, "Contract paused");
    }

    function logUnpaused(address _by) external onlyCenter {
        _writeRecord(ActionType.CONTRACT_UNPAUSED, _by, address(0), 0, "Contract unpaused");
    }

    // ─────────────────────────────────────────────────────────────
    //  INTERNAL WRITE
    // ─────────────────────────────────────────────────────────────

    function _writeRecord(
        ActionType _action,
        address    _actor,
        address    _target,
        uint256    _amount,
        string memory _note
    ) internal {
        uint256 id = recordCount;

        auditLog.push(AuditRecord({
            id:          id,
            action:      _action,
            actor:       _actor,
            target:      _target,
            amount:      _amount,
            note:        _note,
            timestamp:   block.timestamp,
            blockNumber: block.number
        }));

        recordCount++;
        emit AuditRecordCreated(id, _action, _actor, block.timestamp);
    }

    // ─────────────────────────────────────────────────────────────
    //  QUERY FUNCTIONS
    // ─────────────────────────────────────────────────────────────

    /// @notice Get a single audit record by ID
    function getRecord(uint256 _id) external view returns (AuditRecord memory) {
        require(_id < recordCount, "Record does not exist");
        return auditLog[_id];
    }

    /// @notice Get all records for a specific address (actor or target)
    function getRecordsByAddress(address _addr) external view returns (AuditRecord[] memory) {
        // Count matching records first
        uint256 matchCount = 0;
        for (uint256 i = 0; i < auditLog.length; i++) {
            if (auditLog[i].actor == _addr || auditLog[i].target == _addr) {
                matchCount++;
            }
        }

        // Build result array
        AuditRecord[] memory results = new AuditRecord[](matchCount);
        uint256 idx = 0;
        for (uint256 i = 0; i < auditLog.length; i++) {
            if (auditLog[i].actor == _addr || auditLog[i].target == _addr) {
                results[idx] = auditLog[i];
                idx++;
            }
        }
        return results;
    }

    /// @notice Get all records of a specific action type
    function getRecordsByAction(ActionType _action) external view returns (AuditRecord[] memory) {
        uint256 matchCount = 0;
        for (uint256 i = 0; i < auditLog.length; i++) {
            if (auditLog[i].action == _action) matchCount++;
        }

        AuditRecord[] memory results = new AuditRecord[](matchCount);
        uint256 idx = 0;
        for (uint256 i = 0; i < auditLog.length; i++) {
            if (auditLog[i].action == _action) {
                results[idx] = auditLog[i];
                idx++;
            }
        }
        return results;
    }

    /// @notice Get all records (use for small datasets / testing)
    function getAllRecords() external view returns (AuditRecord[] memory) {
        return auditLog;
    }

    /// @notice Get latest N records
    function getLatestRecords(uint256 n) external view returns (AuditRecord[] memory) {
        uint256 total = auditLog.length;
        if (n > total) n = total;

        AuditRecord[] memory results = new AuditRecord[](n);
        for (uint256 i = 0; i < n; i++) {
            results[i] = auditLog[total - n + i];
        }
        return results;
    }

    // ─────────────────────────────────────────────────────────────
    //  HELPER: Convert uint to string (for notes)
    // ─────────────────────────────────────────────────────────────

    function _uint2str(uint256 _i) internal pure returns (string memory) {
        if (_i == 0) return "0";
        uint256 j = _i;
        uint256 len;
        while (j != 0) { len++; j /= 10; }
        bytes memory bstr = new bytes(len);
        uint256 k = len;
        while (_i != 0) {
            k = k - 1;
            uint8 temp = (48 + uint8(_i - _i / 10 * 10));
            bstr[k] = bytes1(temp);
            _i /= 10;
        }
        return string(bstr);
    }
}
