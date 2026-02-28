// =============================================================
//   REMIX INTERACTION SCRIPT
//   File: scripts/interact.js
//
//   HOW TO RUN:
//   1. Deploy AllowanceCenterWithAudit.sol in Remix
//   2. Copy the deployed contract address below
//   3. Open Remix's "File Explorer" → scripts/ → this file
//   4. Right-click → "Run" OR use the Remix terminal
//
//   NOTE: This uses Remix's built-in `ethers` object
//         No npm install needed!
// =============================================================

(async () => {

    // ── STEP 1: Paste your deployed contract address here ──────
    const CONTRACT_ADDRESS = "0xPasteYourContractAddressHere";

    // ── ABI (copy from Remix "Compilation Details" tab) ────────
    // This is a minimal ABI for the key functions
    const ABI = [
        // Write functions
        "function addManager(address _m) external",
        "function removeManager(address _m) external",
        "function registerBeneficiary(address _r) external",
        "function removeBeneficiary(address _r) external",
        "function donate() external payable",
        "function withdraw() external",
        "function pause() external",
        "function unpause() external",

        // Read functions
        "function owner() view returns (address)",
        "function getBeneficiaries() view returns (address[])",
        "function getManagers() view returns (address[])",
        "function getBeneficiaryCount() view returns (uint256)",
        "function getContractBalance() view returns (uint256)",
        "function pendingBalance(address) view returns (uint256)",
        "function lifetimeReceived(address) view returns (uint256)",
        "function totalDonated() view returns (uint256)",
        "function totalDistributed() view returns (uint256)",
        "function paused() view returns (bool)",
        "function getAuditSummary() view returns (uint256,uint256,uint256,uint256,uint256,uint256,bool,uint256)",
        "function previewDistribution(uint256) view returns (uint256)",
        "function getLoggerAddress() view returns (address)",

        // Events
        "event DonationReceived(address indexed from, uint256 amountWei, uint256 numBeneficiaries)",
        "event Withdrawal(address indexed refugee, uint256 amountWei)",
        "event BeneficiaryRegistered(address indexed refugee)",
        "event FundsDistributed(uint256 totalWei, uint256 shareWei, uint256 numBeneficiaries)"
    ];

    // ── STEP 2: Get signer from Remix's injected provider ──────
    const provider = new ethers.providers.Web3Provider(web3Provider);
    const signer   = provider.getSigner();
    const myAddr   = await signer.getAddress();

    console.log("=".repeat(50));
    console.log("  AllowanceCenter Interaction Script");
    console.log("=".repeat(50));
    console.log("Connected wallet:", myAddr);

    // ── STEP 3: Connect to contract ────────────────────────────
    const contract = new ethers.Contract(CONTRACT_ADDRESS, ABI, signer);

    // ── STEP 4: Read current state ─────────────────────────────
    console.log("\n📊 CURRENT STATE:");
    const summary = await contract.getAuditSummary();
    console.log("  Total Donated:     ", ethers.utils.formatEther(summary[0]), "ETH");
    console.log("  Total Distributed: ", ethers.utils.formatEther(summary[1]), "ETH");
    console.log("  Total Withdrawn:   ", ethers.utils.formatEther(summary[2]), "ETH");
    console.log("  Contract Balance:  ", ethers.utils.formatEther(summary[3]), "ETH");
    console.log("  Beneficiary Count: ", summary[4].toString());
    console.log("  Manager Count:     ", summary[5].toString());
    console.log("  Is Paused:         ", summary[6]);
    console.log("  Audit Records:     ", summary[7].toString());

    // ── STEP 5: Demo sequence ───────────────────────────────────
    // Uncomment each block ONE AT A TIME to test:

    // --- Register a beneficiary ---
    /*
    const refugeeAddress = "0xRefugeeAddressHere";
    console.log("\n👤 Registering beneficiary:", refugeeAddress);
    const tx1 = await contract.registerBeneficiary(refugeeAddress);
    await tx1.wait();
    console.log("✅ Registered! TX:", tx1.hash);
    console.log("   View on Etherscan: https://sepolia.etherscan.io/tx/" + tx1.hash);
    */

    // --- Preview distribution ---
    /*
    const donationAmount = ethers.utils.parseEther("0.1"); // 0.1 ETH
    const share = await contract.previewDistribution(donationAmount);
    console.log("\n🔍 If you donate 0.1 ETH:");
    const count = await contract.getBeneficiaryCount();
    console.log("   Beneficiary count:", count.toString());
    console.log("   Each would get:   ", ethers.utils.formatEther(share), "ETH");
    */

    // --- Donate ---
    /*
    const donationWei = ethers.utils.parseEther("0.05");
    console.log("\n💰 Donating 0.05 ETH...");
    const tx2 = await contract.donate({ value: donationWei });
    const receipt2 = await tx2.wait();
    console.log("✅ Donated! TX:", tx2.hash);
    console.log("   Gas used:", receipt2.gasUsed.toString());
    console.log("   View on Etherscan: https://sepolia.etherscan.io/tx/" + tx2.hash);
    */

    // --- Check beneficiary balance ---
    /*
    const refugeeAddr = "0xRefugeeAddressHere";
    const bal = await contract.pendingBalance(refugeeAddr);
    console.log("\n💳 Pending balance for refugee:", ethers.utils.formatEther(bal), "ETH");
    */

    // --- Withdraw (run this from beneficiary account) ---
    /*
    console.log("\n🏧 Withdrawing allowance...");
    const tx3 = await contract.withdraw();
    await tx3.wait();
    console.log("✅ Withdrawn! TX:", tx3.hash);
    */

    // ── STEP 6: Listen for Events ───────────────────────────────
    console.log("\n👂 Listening for events (10 seconds)...");

    contract.on("DonationReceived", (from, amount, count, event) => {
        console.log(`\n🔔 DONATION EVENT:`);
        console.log(`   From: ${from}`);
        console.log(`   Amount: ${ethers.utils.formatEther(amount)} ETH`);
        console.log(`   Beneficiaries: ${count.toString()}`);
        console.log(`   TX: https://sepolia.etherscan.io/tx/${event.transactionHash}`);
    });

    contract.on("Withdrawal", (refugee, amount, event) => {
        console.log(`\n🔔 WITHDRAWAL EVENT:`);
        console.log(`   Refugee: ${refugee}`);
        console.log(`   Amount: ${ethers.utils.formatEther(amount)} ETH`);
    });

    // Stop listening after 10s
    await new Promise(r => setTimeout(r, 10000));
    contract.removeAllListeners();

    console.log("\n✅ Script complete!");
    console.log("=".repeat(50));

})();
