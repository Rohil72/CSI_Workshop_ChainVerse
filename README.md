# 🏕️ Refugee Allowance Center — Blockchain Audit System

A transparent, immutable blockchain-based fund distribution system built for Sepolia Testnet using Remix IDE.

---

## 📁 Project Structure

```
allowance-center/
├── contracts/
│   ├── AllowanceCenterWithAudit.sol   ← DEPLOY THIS (full system in one file)
│   ├── AllowanceCenter.sol             ← Core contract (standalone version)
│   └── AuditLogger.sol                 ← Audit logger (standalone version)
│
├── scripts/
│   └── interact.js                     ← Remix scripting console helper
│
├── analytics/
│   ├── visualize_chain.py              ← Fetch & chart Etherscan transactions
│   └── price_feed.py                   ← Live ETH/USD price tracker
│
└── README.md                           ← You are here
```

---

## 👥 Roles

| Role | Description | Key Permissions |
|---|---|---|
| **Owner** | Contract deployer | Add/remove managers, pause, emergency withdraw |
| **Manager** | NGO staff / camp admin | Register & remove beneficiaries |
| **Benefactor** | Anyone who donates | Call `donate()` with ETH attached |
| **Beneficiary** | Registered refugee | Call `withdraw()` to receive allowance |

---

## 🔄 Workflow

```
1. Owner deploys AllowanceCenterWithAudit.sol
2. Owner adds Manager(s) via addManager()
3. Manager registers Refugees via registerBeneficiary()
4. Benefactor donates ETH via donate() — value auto-splits equally
5. Each Refugee's pendingBalance increases
6. Refugee calls withdraw() to receive their ETH
7. Every step emits an Event → visible on Sepolia Etherscan
8. AuditLogger stores permanent on-chain records
```

---

## 🚀 Deploying on Remix IDE

### Step 1 — Open Remix
Go to: **https://remix.ethereum.org**

### Step 2 — Create the File
- In the left sidebar → **File Explorer** → click the "+" icon
- Name it: `AllowanceCenterWithAudit.sol`
- Paste the contents of `contracts/AllowanceCenterWithAudit.sol`

### Step 3 — Compile
- Click the **Solidity Compiler** icon (second icon in left sidebar)
- Set compiler version to **0.8.19**
- Click **"Compile AllowanceCenterWithAudit.sol"**
- ✅ Green checkmark = success

### Step 4 — Connect MetaMask to Sepolia
- Open MetaMask → Settings → Networks → Add Sepolia
- Get test ETH from: https://sepoliafaucet.com

### Step 5 — Deploy
- Click the **Deploy & Run** icon (third icon)
- Environment: **"Injected Provider - MetaMask"**
- Make sure MetaMask is on **Sepolia** network
- Under "Contract" select: `AllowanceCenterWithAudit`
- Click **"Deploy"** → Confirm MetaMask popup
- 🎉 Contract is live! Copy the address shown in "Deployed Contracts"

---

## 🧪 Testing in Remix (Step by Step)

### As Owner — Add a Manager
```
1. In Deployed Contracts, expand your contract
2. Find: addManager
3. Input: [paste a MetaMask address]
4. Click addManager → Confirm MetaMask
5. Check Remix console — you'll see the event log
```

### As Manager — Register a Refugee
```
1. Find: registerBeneficiary
2. Input: [paste refugee's wallet address]
3. Click registerBeneficiary → Confirm
4. Verify: getBeneficiaries() → should show the address
```

### As Benefactor — Donate
```
1. At the TOP of Remix Deploy panel, set "Value" to 0.05 ETH
2. Find: donate
3. Click donate (with value set above) → Confirm MetaMask
4. Check: getContractBalance() → should show 0.05 ETH
5. Check: pendingBalance([refugee address]) → should show their share
```

### As Refugee — Withdraw
```
1. Switch MetaMask to the refugee's account
2. Find: withdraw
3. Click withdraw → Confirm MetaMask
4. Refugee's wallet balance increases by their share
```

### View Audit Trail
```
1. Find: getAuditSummary() — shows global stats
2. Go to Sepolia Etherscan: https://sepolia.etherscan.io
3. Paste your contract address in the search bar
4. Click "Events" tab → see all logged events
```

---

## 🔍 Key Functions Reference

### Write Functions (cost gas)

| Function | Who Can Call | What It Does |
|---|---|---|
| `addManager(address)` | Owner | Grants manager role |
| `removeManager(address)` | Owner | Revokes manager role |
| `pause()` | Owner | Freezes all operations |
| `unpause()` | Owner | Resumes operations |
| `emergencyWithdraw()` | Owner | Pulls all ETH to owner (last resort) |
| `registerBeneficiary(address)` | Manager | Adds a refugee |
| `removeBeneficiary(address)` | Manager | Removes a refugee |
| `donate()` | Anyone | Send ETH — auto-distributes |
| `withdraw()` | Registered Beneficiary | Receive pending ETH |

### Read Functions (free, no gas)

| Function | Returns |
|---|---|
| `getAuditSummary()` | Full stats snapshot |
| `getBeneficiaries()` | Array of all registered refugees |
| `getManagers()` | Array of all managers |
| `pendingBalance(address)` | How much a refugee can withdraw |
| `lifetimeReceived(address)` | All-time received by a refugee |
| `previewDistribution(uint256)` | Simulates share per person for X Wei |
| `getContractBalance()` | Current ETH in contract |

---

## 📊 Running the Analytics Scripts

### Setup
```bash
pip install requests pandas matplotlib
```

### Visualize Transactions
```bash
cd analytics/
# Edit visualize_chain.py — set CONTRACT_ADDRESS and ETHERSCAN_API_KEY
python visualize_chain.py
```

### Live ETH Price Tracker
```bash
# Single check:
python price_feed.py

# Continuous tracking (updates every 15s):
python price_feed.py --live
```

---

## 📋 Audit & Transparency

Every action creates an **immutable on-chain audit record** via the embedded `AuditLogger`:

- `MANAGER_ADDED` / `MANAGER_REMOVED`
- `BENEFICIARY_REGISTERED` / `BENEFICIARY_REMOVED`
- `DONATION_RECEIVED`
- `FUNDS_DISTRIBUTED`
- `WITHDRAWAL`
- `CONTRACT_PAUSED` / `CONTRACT_UNPAUSED`

Each record stores: **who did it, who was affected, how much, when, and on which block.**

To view: `logger.getAllRecords()` or `logger.getRecordsByAddress(address)`

The logger contract address is available via: `getLoggerAddress()`

---

## ⚠️ Important Notes

- **Dust**: Integer division (e.g. 10 Wei ÷ 3 refugees = 3 Wei each, 1 Wei stays in contract). This is expected.
- **Re-entrancy**: `pendingBalance` is zeroed BEFORE transfer — safe against re-entrancy attacks.
- **Gas**: Each donation call costs gas proportional to the number of beneficiaries. Keep lists manageable.
- **Stablecoins**: This version uses ETH directly. For production, integrate Uniswap V3 to convert ETH → USDC at donation time (see `price_feed.py` for why this matters).

---

## 🔗 Useful Links

| Resource | Link |
|---|---|
| Remix IDE | https://remix.ethereum.org |
| Sepolia Faucet | https://sepoliafaucet.com |
| Sepolia Etherscan | https://sepolia.etherscan.io |
| Etherscan API | https://etherscan.io/apis |
| CoinGecko API | https://www.coingecko.com/api |
| Solidity Docs | https://docs.soliditylang.org |

---

*Built for educational purposes on Sepolia Testnet.*
