"""
=============================================================
  ALLOWANCE CENTER - CHAIN VISUALIZER
  File: analytics/visualize_chain.py

  WHAT THIS DOES:
    1. Fetches all transactions from your contract
    2. Fetches live ETH/USD price from CoinGecko (free, no key)
    3. Prints a terminal blockchain-contents report
    4. Creates a 6-panel dashboard:
       - Donation history over time
       - Cumulative USD value raised
       - Transaction type breakdown (pie chart)
       - Top donors bar chart
       - Daily on-chain interactions
       - Gas usage by transaction

  HOW TO RUN:
    pip install requests pandas matplotlib
    python visualize_chain.py

  SETUP:
    1. Get a free API key from https://etherscan.io
    2. Paste your contract address below
    3. Run the script
=============================================================
"""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests

# --- YOUR CONFIG ---------------------------------------------------------------
ETHERSCAN_API_KEY = ""  # Free at etherscan.io
CONTRACT_ADDRESS = ""  # From Remix deploy
NETWORK = "sepolia"  # "sepolia" or "mainnet"

CHAIN_ID = "11155111" if NETWORK == "sepolia" else "1"
BASE_URL = "https://api.etherscan.io/v2/api"


def short_addr(addr: str, left: int = 6, right: int = 4) -> str:
    """Shorten an Ethereum address for terminal and chart labels."""
    if not isinstance(addr, str) or len(addr) < (left + right + 3):
        return str(addr)
    return f"{addr[:left]}...{addr[-right:]}"


def fetch_transactions(address: str) -> pd.DataFrame:
    """Fetch all normal transactions for the contract."""
    params = {
        "chainid": CHAIN_ID,
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
        "apikey": ETHERSCAN_API_KEY,
    }

    print(f"Fetching transactions for {address[:8]}...{address[-6:]}")
    response = requests.get(BASE_URL, params=params, timeout=12)
    data = response.json()

    if data.get("status") != "1":
        print(f"No transactions found or API error: {data.get('message')}")
        print(f"Result: {data.get('result')}")
        return pd.DataFrame()

    txns = data["result"]
    print(f"Found {len(txns)} transactions")

    df = pd.DataFrame(txns)
    df["value_wei"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    df["value_eth"] = df["value_wei"] / 1e18
    df["timestamp"] = pd.to_datetime(
        pd.to_numeric(df["timeStamp"], errors="coerce"), unit="s"
    )
    df["gas_used"] = pd.to_numeric(df["gasUsed"], errors="coerce").fillna(0).astype(int)
    df["block_num"] = (
        pd.to_numeric(df["blockNumber"], errors="coerce").fillna(0).astype(int)
    )
    df["is_incoming"] = df["to"].fillna("").str.lower() == address.lower()
    df["is_error"] = (
        pd.to_numeric(df["isError"], errors="coerce").fillna(0).astype(int) == 1
    )

    return df


def fetch_internal_transactions(address: str) -> pd.DataFrame:
    """Fetch internal transactions for the contract (captures beneficiary payouts)."""
    params = {
        "chainid": CHAIN_ID,
        "module": "account",
        "action": "txlistinternal",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
        "apikey": ETHERSCAN_API_KEY,
    }

    response = requests.get(BASE_URL, params=params, timeout=12)
    data = response.json()
    if data.get("status") != "1":
        return pd.DataFrame()

    df = pd.DataFrame(data["result"])
    if df.empty:
        return df

    df["value_wei"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    df["value_eth"] = df["value_wei"] / 1e18
    df["timestamp"] = pd.to_datetime(
        pd.to_numeric(df["timeStamp"], errors="coerce"), unit="s"
    )
    df["is_error"] = (
        pd.to_numeric(df["isError"], errors="coerce").fillna(0).astype(int) == 1
    )
    df["from"] = df["from"].fillna("").str.lower()
    df["to"] = df["to"].fillna("").str.lower()
    return df


def get_eth_usd_price() -> float:
    """Get current ETH price in USD from CoinGecko (no API key needed)."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        res = requests.get(
            url, params={"ids": "ethereum", "vs_currencies": "usd"}, timeout=6
        )
        price = float(res.json()["ethereum"]["usd"])
        print(f"Live ETH Price: ${price:,.2f}")
        return price
    except Exception as exc:
        print(f"Could not fetch live price ({exc}). Using $2000 fallback.")
        return 2000.0


def print_summary(df: pd.DataFrame, internal_df: pd.DataFrame, eth_price: float):
    """Print a clean text summary to the console."""
    if df.empty:
        print("No data to summarize.")
        return

    incoming = df[df["is_incoming"] & (df["value_eth"] > 0) & ~df["is_error"]]
    if internal_df.empty:
        outgoing = pd.DataFrame()
    else:
        outgoing = internal_df[
            (internal_df["from"] == CONTRACT_ADDRESS.lower())
            & (internal_df["value_eth"] > 0)
            & ~internal_df["is_error"]
        ]
    zero_value_calls = df[(df["value_eth"] == 0) & ~df["is_error"]]

    total_donated_eth = incoming["value_eth"].sum()
    total_donated_usd = total_donated_eth * eth_price
    unique_donors = incoming["from"].nunique() if not incoming.empty else 0

    print("\n" + "=" * 60)
    print("  ALLOWANCE CENTER - AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Contract:              {short_addr(CONTRACT_ADDRESS, 8, 6)}")
    print(f"  Network:               {NETWORK.title()}")
    print(f"  ETH Price (live):      ${eth_price:,.2f} USD")
    print("-" * 60)
    print(f"  Total Transactions:    {len(df)}")
    print(f"  Successful:            {len(df[~df['is_error']])}")
    print(f"  Failed:                {len(df[df['is_error']])}")
    print(f"  Contract Calls (0ETH): {len(zero_value_calls)}")
    print("-" * 60)
    print(f"  Donations Received:    {len(incoming)}")
    print(f"  Unique Donors:         {unique_donors}")
    print(f"  Total Donated (ETH):   {total_donated_eth:.6f} ETH")
    print(f"  Total Donated (USD):   ${total_donated_usd:,.2f}")
    print(f"  Withdrawals:           {len(outgoing)}")
    print("=" * 60 + "\n")


def print_chain_contents(
    df: pd.DataFrame, internal_df: pd.DataFrame, max_rows: int = 12
):
    """Print a compact blockchain contents report to the terminal."""
    if df.empty:
        print("No blockchain contents available.")
        return

    print("=" * 95)
    print("  CHAIN CONTENTS (LATEST TRANSACTIONS)")
    print("=" * 95)
    print(f"  Blocks covered: {df['block_num'].min()} -> {df['block_num'].max()}")
    print(f"  Time range:     {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print("-" * 95)
    print(
        f"{'Block':>8} {'Time':>19} {'Type':>11} {'Value(ETH)':>12} {'Gas':>8} {'From':>15} {'To':>15}"
    )
    print("-" * 95)

    recent = df.sort_values("timestamp", ascending=False).head(max_rows).copy()
    for _, row in recent.iterrows():
        if row["is_error"]:
            tx_type = "FAILED"
        elif row["is_incoming"] and row["value_eth"] > 0:
            tx_type = "DONATION"
        elif (not row["is_incoming"]) and row["value_eth"] > 0:
            tx_type = "WITHDRAW"
        else:
            tx_type = "CALL(0ETH)"

        to_addr = row["to"] if row["to"] else "<create>"
        print(
            f"{int(row['block_num']):>8} "
            f"{row['timestamp'].strftime('%Y-%m-%d %H:%M'):>19} "
            f"{tx_type:>11} "
            f"{row['value_eth']:>12.6f} "
            f"{int(row['gas_used']):>8} "
            f"{short_addr(row['from']):>15} "
            f"{short_addr(to_addr):>15}"
        )

    print("-" * 95)
    print("  Recent tx hashes:")
    for tx_hash in recent["hash"].head(6):
        print(f"    - {tx_hash}")
    if not internal_df.empty:
        withdrawals = internal_df[
            (internal_df["from"] == CONTRACT_ADDRESS.lower())
            & (internal_df["value_eth"] > 0)
            & ~internal_df["is_error"]
        ].sort_values("timestamp", ascending=False)
        if not withdrawals.empty:
            print("  Recent withdrawal traces:")
            for _, row in withdrawals.head(6).iterrows():
                print(
                    f"    - {row['timestamp']}  {row['value_eth']:.6f} ETH  -> {short_addr(row['to'])}"
                )
    print("=" * 95 + "\n")


def create_charts(df: pd.DataFrame, internal_df: pd.DataFrame, eth_price: float):
    """Create a 6-panel visualization and save to PNG."""
    if df.empty:
        print("No data to visualize.")
        return

    incoming = df[df["is_incoming"] & (df["value_eth"] > 0) & ~df["is_error"]].copy()
    if internal_df.empty:
        outgoing = pd.DataFrame()
    else:
        outgoing = internal_df[
            (internal_df["from"] == CONTRACT_ADDRESS.lower())
            & (internal_df["value_eth"] > 0)
            & ~internal_df["is_error"]
        ].copy()
    successful_calls = df[(df["value_eth"] == 0) & ~df["is_error"]].copy()

    if not incoming.empty:
        incoming["value_usd"] = incoming["value_eth"] * eth_price
        incoming["cumulative_usd"] = incoming["value_usd"].cumsum()

    fig, axes = plt.subplots(3, 2, figsize=(15, 13))
    fig.patch.set_facecolor("#0f172a")
    fig.suptitle(
        "Refugee Allowance Center - Blockchain Audit Dashboard\n"
        f"Contract: {short_addr(CONTRACT_ADDRESS, 8, 6)} | {NETWORK.title()} | ETH=${eth_price:,.0f}",
        fontsize=13,
        fontweight="bold",
        color="white",
        y=0.98,
    )

    colors = {
        "blue": "#3b82f6",
        "green": "#22c55e",
        "red": "#ef4444",
        "orange": "#f97316",
        "purple": "#a855f7",
        "bg": "#1e293b",
        "text": "#e2e8f0",
        "grid": "#334155",
    }

    def style_ax(ax, title):
        ax.set_facecolor(colors["bg"])
        ax.set_title(title, color=colors["text"], fontsize=11, pad=10)
        ax.tick_params(colors=colors["text"], labelsize=8)
        ax.grid(alpha=0.3, color=colors["grid"])
        for spine in ax.spines.values():
            spine.set_edgecolor(colors["grid"])

    ax1 = axes[0][0]
    if incoming.empty:
        ax1.text(
            0.5,
            0.5,
            "No incoming ETH donations yet",
            ha="center",
            va="center",
            color=colors["text"],
            transform=ax1.transAxes,
        )
    else:
        ax1.bar(
            incoming["timestamp"],
            incoming["value_eth"],
            color=colors["blue"],
            alpha=0.85,
            width=0.4,
        )
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
    ax1.set_ylabel("ETH", color=colors["text"])
    style_ax(ax1, "Donations Per Transaction (ETH)")
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")

    ax2 = axes[0][1]
    if incoming.empty:
        ax2.text(
            0.5,
            0.5,
            "No cumulative donation value yet",
            ha="center",
            va="center",
            color=colors["text"],
            transform=ax2.transAxes,
        )
    else:
        ax2.plot(
            incoming["timestamp"],
            incoming["cumulative_usd"],
            color=colors["green"],
            linewidth=2.5,
            marker="o",
            markersize=4,
        )
        ax2.fill_between(
            incoming["timestamp"],
            incoming["cumulative_usd"],
            alpha=0.15,
            color=colors["green"],
        )
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2.set_ylabel("USD", color=colors["text"])
    style_ax(ax2, f"Cumulative Donations (USD @ ${eth_price:,.0f}/ETH)")
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")

    ax3 = axes[1][0]
    sizes = [
        len(incoming),
        len(outgoing),
        len(successful_calls),
        len(df[df["is_error"]]),
    ]
    labels = ["Donations", "Withdrawals", "Calls (0 ETH)", "Failed Txns"]
    pie_colors = [colors["blue"], colors["green"], colors["orange"], colors["red"]]
    non_zero = [(s, l, c) for s, l, c in zip(sizes, labels, pie_colors) if s > 0]
    if non_zero:
        s, l, c = zip(*non_zero)
        _, _, autotexts = ax3.pie(
            s,
            labels=l,
            colors=c,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"color": colors["text"]},
            wedgeprops={"edgecolor": colors["bg"], "linewidth": 2},
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(9)
    style_ax(ax3, "Transaction Type Breakdown")
    ax3.grid(False)

    ax4 = axes[1][1]
    donor_totals = (
        incoming.groupby("from")["value_eth"].sum().sort_values(ascending=False).head(8)
    )
    if donor_totals.empty:
        ax4.text(
            0.5,
            0.5,
            "No donor ranking yet",
            ha="center",
            va="center",
            color=colors["text"],
            transform=ax4.transAxes,
        )
    else:
        short_addrs = [short_addr(a) for a in donor_totals.index]
        bars = ax4.barh(
            short_addrs, donor_totals.values, color=colors["orange"], alpha=0.85
        )
        ax4.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
        ax4.set_xlabel("ETH Donated", color=colors["text"])
        ax4.invert_yaxis()
        for bar, val in zip(bars, donor_totals.values):
            ax4.text(
                val + 0.0001,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.4f}",
                va="center",
                color=colors["text"],
                fontsize=7,
            )
    style_ax(ax4, "Top Donors by ETH Contributed")
    ax4.yaxis.tick_right()

    ax5 = axes[2][0]
    tx_per_day = df.set_index("timestamp").resample("D").size()
    tx_per_day = tx_per_day[tx_per_day > 0]
    if tx_per_day.empty:
        ax5.text(
            0.5,
            0.5,
            "No daily interaction data",
            ha="center",
            va="center",
            color=colors["text"],
            transform=ax5.transAxes,
        )
    else:
        ax5.plot(
            tx_per_day.index,
            tx_per_day.values,
            color=colors["purple"],
            linewidth=2.2,
            marker="o",
            markersize=4,
        )
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax5.set_ylabel("Transactions", color=colors["text"])
    style_ax(ax5, "Daily Contract Interactions")
    plt.setp(ax5.xaxis.get_majorticklabels(), rotation=30, ha="right")

    ax6 = axes[2][1]
    ax6.scatter(
        df["block_num"],
        df["gas_used"],
        c=df["is_error"].map({True: colors["red"], False: colors["blue"]}),
        alpha=0.8,
        s=40,
    )
    ax6.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax6.set_xlabel("Block Number", color=colors["text"])
    ax6.set_ylabel("Gas Used", color=colors["text"])
    style_ax(ax6, "Gas Used by Transaction (Red=Failed)")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    output_file = "allowance_center_audit.png"
    plt.savefig(
        output_file, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor()
    )
    plt.show()
    print(f"\nChart saved to: {output_file}")


def export_csv(df: pd.DataFrame, internal_df: pd.DataFrame, eth_price: float):
    """Export a clean audit CSV with USD values."""
    if df.empty:
        return

    export = df[
        [
            "hash",
            "timestamp",
            "from",
            "to",
            "value_eth",
            "is_incoming",
            "is_error",
            "gas_used",
            "block_num",
        ]
    ].copy()
    export["value_usd"] = export["value_eth"] * eth_price
    export["direction"] = export["is_incoming"].map(
        {True: "INCOMING", False: "OUTGOING"}
    )
    export["tx_type"] = "CALL_0_ETH"
    export.loc[
        (export["direction"] == "INCOMING") & (export["value_eth"] > 0), "tx_type"
    ] = "DONATION"
    export.loc[
        (export["direction"] == "OUTGOING") & (export["value_eth"] > 0), "tx_type"
    ] = "WITHDRAWAL"
    export.loc[export["is_error"], "tx_type"] = "FAILED"

    explorer_base = (
        "https://sepolia.etherscan.io/tx/"
        if NETWORK == "sepolia"
        else "https://etherscan.io/tx/"
    )
    export["etherscan"] = explorer_base + export["hash"]
    export = export.drop(columns=["is_incoming"])

    if not internal_df.empty:
        withdrawal_rows = internal_df[
            (internal_df["from"] == CONTRACT_ADDRESS.lower())
            & (internal_df["value_eth"] > 0)
            & ~internal_df["is_error"]
        ].copy()
        if not withdrawal_rows.empty:
            withdrawal_rows = withdrawal_rows.rename(columns={"hash": "hash"})
            withdrawal_rows["direction"] = "OUTGOING"
            withdrawal_rows["tx_type"] = "WITHDRAWAL_INTERNAL"
            withdrawal_rows["gas_used"] = (
                pd.to_numeric(withdrawal_rows.get("gasUsed", 0), errors="coerce")
                .fillna(0)
                .astype(int)
            )
            withdrawal_rows["block_num"] = (
                pd.to_numeric(withdrawal_rows.get("blockNumber", 0), errors="coerce")
                .fillna(0)
                .astype(int)
            )
            withdrawal_rows["value_usd"] = withdrawal_rows["value_eth"] * eth_price
            withdrawal_rows["etherscan"] = explorer_base + withdrawal_rows["hash"]
            withdrawal_rows = withdrawal_rows[
                [
                    "hash",
                    "timestamp",
                    "from",
                    "to",
                    "value_eth",
                    "is_error",
                    "gas_used",
                    "block_num",
                    "value_usd",
                    "direction",
                    "tx_type",
                    "etherscan",
                ]
            ]
            export = pd.concat([export, withdrawal_rows], ignore_index=True)

    filename = "audit_export.csv"
    export.to_csv(filename, index=False)
    print(f"Audit CSV exported to: {filename}")


if __name__ == "__main__":
    print("\nAllowance Center - Chain Visualizer")
    print("=" * 45)

    if "YourContractAddress" in CONTRACT_ADDRESS:
        print("Please set CONTRACT_ADDRESS at the top of this file.")
        print("Then re-run: python visualize_chain.py")
        raise SystemExit(1)

    eth_price = get_eth_usd_price()
    df = fetch_transactions(CONTRACT_ADDRESS)
    internal_df = fetch_internal_transactions(CONTRACT_ADDRESS)

    if not df.empty:
        print_summary(df, internal_df, eth_price)
        print_chain_contents(df, internal_df)
        create_charts(df, internal_df, eth_price)
        export_csv(df, internal_df, eth_price)
    else:
        print("\nNo transactions yet. Interact with the contract first, then re-run.")
