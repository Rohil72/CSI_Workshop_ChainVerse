"""
=============================================================
  ALLOWANCE CENTER — CHAIN VISUALIZER
  File: analytics/visualize_chain.py

  WHAT THIS DOES:
    1. Fetches all transactions from your Sepolia contract
    2. Fetches live ETH/USD price from CoinGecko (free, no key)
    3. Creates 4 charts:
       - Donation history over time
       - Cumulative USD value raised
       - Transaction type breakdown (pie chart)
       - Per-beneficiary allocation bar chart

  HOW TO RUN:
    pip install requests pandas matplotlib
    python visualize_chain.py

  SETUP:
    1. Get a free API key from https://etherscan.io
    2. Paste your contract address below
    3. Run the script
=============================================================
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from datetime import datetime
import json

# ─── YOUR CONFIG ────────────────────────────────────────────────
ETHERSCAN_API_KEY = "YOUR_ETHERSCAN_API_KEY"          # Free at etherscan.io
CONTRACT_ADDRESS  = "0xYourContractAddressHere"       # From Remix deploy
NETWORK           = "sepolia"                          # "sepolia" or "mainnet"

BASE_URL = f"https://api-{NETWORK}.etherscan.io/api"


# ─── FETCH: All Transactions ─────────────────────────────────────
def fetch_transactions(address: str) -> pd.DataFrame:
    """Fetch all normal transactions for the contract."""
    params = {
        "module":     "account",
        "action":     "txlist",
        "address":    address,
        "startblock": 0,
        "endblock":   99999999,
        "sort":       "asc",
        "apikey":     ETHERSCAN_API_KEY,
    }

    print(f"📡 Fetching transactions for {address[:8]}...{address[-6:]}")
    response = requests.get(BASE_URL, params=params, timeout=10)
    data = response.json()

    if data["status"] != "1":
        print(f"⚠️  No transactions found or API error: {data.get('message')}")
        return pd.DataFrame()

    txns = data["result"]
    print(f"✅ Found {len(txns)} transactions")

    df = pd.DataFrame(txns)

    # Clean up columns
    df["value_wei"]   = df["value"].astype(float)
    df["value_eth"]   = df["value_wei"] / 1e18
    df["timestamp"]   = pd.to_datetime(df["timeStamp"].astype(int), unit="s")
    df["gas_used"]    = df["gasUsed"].astype(int)
    df["is_incoming"] = df["to"].str.lower() == address.lower()
    df["is_error"]    = df["isError"].astype(int) == 1

    return df


# ─── FETCH: Event Logs (e.g. DonationReceived) ───────────────────
def fetch_event_logs(address: str, event_signature: str) -> list:
    """
    Fetch specific events using their topic hash.
    
    Common topic hashes for AllowanceCenterWithAudit:
      DonationReceived : keccak256("DonationReceived(address,uint256,uint256)")
      Withdrawal       : keccak256("Withdrawal(address,uint256)")
      FundsDistributed : keccak256("FundsDistributed(uint256,uint256,uint256)")
    
    You can compute these at: https://emn178.github.io/online-tools/keccak_256.html
    """
    params = {
        "module":    "logs",
        "action":    "getLogs",
        "address":   address,
        "topic0":    event_signature,
        "apikey":    ETHERSCAN_API_KEY,
    }

    response = requests.get(BASE_URL, params=params, timeout=10)
    data = response.json()
    return data.get("result", [])


# ─── FETCH: Live ETH/USD Price ───────────────────────────────────
def get_eth_usd_price() -> float:
    """Get current ETH price in USD from CoinGecko (no API key needed)."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        res = requests.get(url, params={"ids": "ethereum", "vs_currencies": "usd"}, timeout=5)
        price = res.json()["ethereum"]["usd"]
        print(f"💲 Live ETH Price: ${price:,.2f}")
        return price
    except Exception as e:
        print(f"⚠️  Could not fetch live price ({e}). Using $2000 as fallback.")
        return 2000.0


# ─── PRINT: Console Summary ──────────────────────────────────────
def print_summary(df: pd.DataFrame, eth_price: float):
    """Print a clean text summary to the console."""
    if df.empty:
        print("No data to summarize.")
        return

    incoming = df[df["is_incoming"] & (df["value_eth"] > 0) & ~df["is_error"]]
    outgoing = df[~df["is_incoming"] & (df["value_eth"] > 0) & ~df["is_error"]]

    total_donated_eth = incoming["value_eth"].sum()
    total_donated_usd = total_donated_eth * eth_price
    unique_donors = incoming["from"].nunique() if not incoming.empty else 0

    print("\n" + "=" * 55)
    print("  📋  ALLOWANCE CENTER — AUDIT SUMMARY")
    print("=" * 55)
    print(f"  Contract:          {CONTRACT_ADDRESS[:8]}...{CONTRACT_ADDRESS[-6:]}")
    print(f"  Network:           Sepolia Testnet")
    print(f"  ETH Price (live):  ${eth_price:,.2f} USD")
    print("-" * 55)
    print(f"  Total Transactions:    {len(df)}")
    print(f"  Successful:            {len(df[~df['is_error']])}")
    print(f"  Failed:                {len(df[df['is_error']])}")
    print("-" * 55)
    print(f"  Donations Received:    {len(incoming)}")
    print(f"  Unique Donors:         {unique_donors}")
    print(f"  Total Donated (ETH):   {total_donated_eth:.6f} ETH")
    print(f"  Total Donated (USD):   ${total_donated_usd:,.2f}")
    print(f"  Withdrawals:           {len(outgoing)}")
    print("=" * 55 + "\n")


# ─── VISUALIZE: 4-Panel Chart ────────────────────────────────────
def create_charts(df: pd.DataFrame, eth_price: float):
    """Create a 4-panel visualization and save to PNG."""
    if df.empty:
        print("⚠️  No data to visualize.")
        return

    incoming = df[df["is_incoming"] & (df["value_eth"] > 0) & ~df["is_error"]].copy()
    outgoing = df[~df["is_incoming"] & (df["value_eth"] > 0) & ~df["is_error"]].copy()

    if incoming.empty:
        print("⚠️  No donation transactions to chart.")
        return

    # Convert to USD
    incoming["value_usd"]        = incoming["value_eth"] * eth_price
    incoming["cumulative_eth"]   = incoming["value_eth"].cumsum()
    incoming["cumulative_usd"]   = incoming["value_usd"].cumsum()

    # ── Figure Setup ─────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor("#0f172a")  # Dark background
    fig.suptitle(
        "Refugee Allowance Center — Blockchain Audit Dashboard\n"
        f"Contract: {CONTRACT_ADDRESS[:8]}...{CONTRACT_ADDRESS[-6:]}  |  Sepolia Testnet  |  ETH=${eth_price:,.0f}",
        fontsize=13, fontweight="bold", color="white", y=0.98
    )

    colors = {
        "blue":   "#3b82f6",
        "green":  "#22c55e",
        "red":    "#ef4444",
        "orange": "#f97316",
        "purple": "#a855f7",
        "bg":     "#1e293b",
        "text":   "#e2e8f0",
        "grid":   "#334155"
    }

    def style_ax(ax, title):
        ax.set_facecolor(colors["bg"])
        ax.set_title(title, color=colors["text"], fontsize=11, pad=10)
        ax.tick_params(colors=colors["text"], labelsize=8)
        ax.grid(alpha=0.3, color=colors["grid"])
        for spine in ax.spines.values():
            spine.set_edgecolor(colors["grid"])

    # ── Chart 1: Donation Bar Chart ───────────────────────────────
    ax1 = axes[0][0]
    ax1.bar(incoming["timestamp"], incoming["value_eth"],
            color=colors["blue"], alpha=0.85, width=0.4)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
    ax1.set_ylabel("ETH", color=colors["text"])
    style_ax(ax1, "📥 Donations Per Transaction (ETH)")
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")

    # ── Chart 2: Cumulative USD ────────────────────────────────────
    ax2 = axes[0][1]
    ax2.plot(incoming["timestamp"], incoming["cumulative_usd"],
             color=colors["green"], linewidth=2.5, marker="o", markersize=4)
    ax2.fill_between(incoming["timestamp"], incoming["cumulative_usd"],
                     alpha=0.15, color=colors["green"])
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2.set_ylabel("USD", color=colors["text"])
    style_ax(ax2, f"💵 Cumulative Donations (USD @ ${eth_price:,.0f}/ETH)")
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")

    # ── Chart 3: Pie — Transaction Types ──────────────────────────
    ax3 = axes[1][0]
    sizes  = [len(incoming), len(outgoing), len(df[df["is_error"]])]
    labels = ["Donations", "Withdrawals", "Failed Txns"]
    pie_colors = [colors["blue"], colors["green"], colors["red"]]
    non_zero = [(s, l, c) for s, l, c in zip(sizes, labels, pie_colors) if s > 0]

    if non_zero:
        s, l, c = zip(*non_zero)
        wedges, texts, autotexts = ax3.pie(
            s, labels=l, colors=c, autopct="%1.1f%%",
            startangle=90, textprops={"color": colors["text"]},
            wedgeprops={"edgecolor": colors["bg"], "linewidth": 2}
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(9)
    style_ax(ax3, "🍕 Transaction Type Breakdown")
    ax3.grid(False)

    # ── Chart 4: Top Donors Bar ────────────────────────────────────
    ax4 = axes[1][1]
    donor_totals = incoming.groupby("from")["value_eth"].sum().sort_values(ascending=False).head(8)

    if not donor_totals.empty:
        # Shorten addresses for display
        short_addrs = [f"{a[:6]}...{a[-4:]}" for a in donor_totals.index]
        bars = ax4.barh(short_addrs, donor_totals.values, color=colors["orange"], alpha=0.85)
        ax4.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
        ax4.set_xlabel("ETH Donated", color=colors["text"])
        ax4.invert_yaxis()
        # Add value labels
        for bar, val in zip(bars, donor_totals.values):
            ax4.text(val + 0.0001, bar.get_y() + bar.get_height()/2,
                     f"{val:.4f}", va="center", color=colors["text"], fontsize=7)

    style_ax(ax4, "🏆 Top Donors by ETH Contributed")
    ax4.yaxis.tick_right()

    # ── Save ──────────────────────────────────────────────────────
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    output_file = "allowance_center_audit.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.show()
    print(f"\n✅ Chart saved to: {output_file}")


# ─── EXPORT: Audit CSV ───────────────────────────────────────────
def export_csv(df: pd.DataFrame, eth_price: float):
    """Export a clean audit CSV with USD values."""
    if df.empty:
        return

    export = df[[
        "hash", "timestamp", "from", "to",
        "value_eth", "is_incoming", "is_error", "gas_used"
    ]].copy()

    export["value_usd"]  = export["value_eth"] * eth_price
    export["direction"]  = export["is_incoming"].map({True: "INCOMING", False: "OUTGOING"})
    export["etherscan"]  = "https://sepolia.etherscan.io/tx/" + export["hash"]
    export = export.drop(columns=["is_incoming"])

    filename = "audit_export.csv"
    export.to_csv(filename, index=False)
    print(f"📄 Audit CSV exported to: {filename}")


# ─── MAIN ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀 Allowance Center — Chain Visualizer")
    print("=" * 45)

    if "YourContractAddress" in CONTRACT_ADDRESS:
        print("⚠️  Please set CONTRACT_ADDRESS at the top of this file!")
        print("    Then re-run: python visualize_chain.py")
        exit(1)

    eth_price = get_eth_usd_price()
    df = fetch_transactions(CONTRACT_ADDRESS)

    if not df.empty:
        print_summary(df, eth_price)
        create_charts(df, eth_price)
        export_csv(df, eth_price)
    else:
        print("\nℹ️  No transactions yet. Donate to the contract first, then re-run!")
