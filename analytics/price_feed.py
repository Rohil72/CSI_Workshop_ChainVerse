"""
=============================================================
  ETH / BTC → STABLECOIN PRICE TRACKER
  File: analytics/price_feed.py

  WHAT THIS DOES:
    - Fetches live ETH and BTC prices from CoinGecko (free, no key)
    - Shows what a donation of X ETH is worth in USD/USDC
    - Simulates how the AllowanceCenter would convert donations
    - Saves a price history chart

  WHY THIS MATTERS:
    ETH can swing ±20% in a day. If a refugee receives 0.1 ETH
    when ETH = $2000, they get $200. But if they wait to withdraw
    and ETH drops to $1600, they only get $160. 
    Stablecoin conversion (ETH → USDC) locks the value at donation time.

  HOW TO RUN:
    pip install requests matplotlib
    python price_feed.py
=============================================================
"""

import requests
import time
import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ─── CONFIG ──────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = 15   # How often to refresh price
MAX_HISTORY_POINTS    = 50   # How many data points to show on chart
DONATION_ETH          = 0.1  # Simulated donation amount

# ─── FETCH: Live Prices ───────────────────────────────────────────

def get_crypto_prices() -> dict:
    """
    Fetch ETH and BTC prices in USD.
    Uses CoinGecko — free, no API key needed.
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "ethereum,bitcoin",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        return {
            "eth_usd":          data["ethereum"]["usd"],
            "eth_24h_change":   data["ethereum"]["usd_24h_change"],
            "btc_usd":          data["bitcoin"]["usd"],
            "btc_24h_change":   data["bitcoin"]["usd_24h_change"],
            "timestamp":        datetime.now()
        }
    except Exception as e:
        print(f"⚠️  Price fetch failed: {e}")
        return None


# ─── SIMULATE: Donation Conversion ────────────────────────────────

def simulate_donation(eth_amount: float, eth_price: float, num_beneficiaries: int = 5) -> dict:
    """
    Simulate how an ETH donation would be distributed in USD terms.
    This mirrors exactly what AllowanceCenterWithAudit does on-chain,
    but converted to USD so beneficiaries know the real value.
    """
    total_usd     = eth_amount * eth_price
    share_eth     = eth_amount / num_beneficiaries
    share_usd     = total_usd / num_beneficiaries
    # Dust = remainder from Wei division (usually tiny, negligible at these amounts)
    dust_wei      = int(eth_amount * 1e18) % num_beneficiaries

    return {
        "donation_eth":      eth_amount,
        "donation_usd":      total_usd,
        "num_beneficiaries": num_beneficiaries,
        "share_eth":         share_eth,
        "share_usd":         share_usd,
        "dust_wei":          dust_wei,
    }


# ─── PRINT: Formatted Output ──────────────────────────────────────

def print_price_update(prices: dict, sim: dict):
    eth_change  = prices["eth_24h_change"]
    btc_change  = prices["btc_24h_change"]
    eth_arrow   = "↑" if eth_change > 0 else "↓"
    btc_arrow   = "↑" if btc_change > 0 else "↓"
    change_sign = "+" if eth_change > 0 else ""

    print("\n" + "─" * 55)
    print(f"  🕐  {prices['timestamp'].strftime('%H:%M:%S')}   |   Live Crypto Prices")
    print("─" * 55)
    print(f"  ETH/USD:  ${prices['eth_usd']:>10,.2f}  {eth_arrow} {change_sign}{eth_change:.2f}% (24h)")
    print(f"  BTC/USD:  ${prices['btc_usd']:>10,.2f}  {btc_arrow} {btc_change:+.2f}% (24h)")
    print("─" * 55)
    print(f"  💰 Donation Simulation ({sim['donation_eth']} ETH → {sim['num_beneficiaries']} refugees):")
    print(f"     Total USD value:       ${sim['donation_usd']:>8.2f}")
    print(f"     Each refugee receives: ${sim['share_usd']:>8.2f}  ({sim['share_eth']:.6f} ETH)")
    print(f"     Dust (stays in pool):  {sim['dust_wei']:>6} Wei")
    print("─" * 55)

    # Volatility warning
    if abs(eth_change) > 5:
        print(f"  ⚠️  HIGH VOLATILITY: ETH moved {abs(eth_change):.1f}% in 24h.")
        print(f"      Consider USDC conversion at donation time for stability.")
    print()


# ─── CHART: Price History ─────────────────────────────────────────

def plot_price_history(history: list, donation_eth: float):
    """
    Plot ETH price history and the USD value of the donation over time.
    Shows why stablecoin conversion is important for refugees.
    """
    if len(history) < 2:
        print("⚠️  Need at least 2 data points to chart.")
        return

    times     = [h["timestamp"] for h in history]
    eth_prices= [h["eth_usd"] for h in history]
    usd_vals  = [p * donation_eth for p in eth_prices]

    # Volatility band
    avg_price = sum(eth_prices) / len(eth_prices)
    band_hi   = avg_price * 1.05  # +5%
    band_lo   = avg_price * 0.95  # -5%

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.patch.set_facecolor("#0f172a")
    fig.suptitle(
        f"ETH Price Tracker — Allowance Center Donation Simulator\n"
        f"Simulated Donation: {donation_eth} ETH",
        fontsize=13, color="white", fontweight="bold"
    )

    DARK_BG = "#1e293b"
    TEXT    = "#e2e8f0"
    GRID    = "#334155"

    # ── ETH Price ────────────────────────────────────────────────
    ax1.set_facecolor(DARK_BG)
    ax1.plot(times, eth_prices, color="#3b82f6", linewidth=2, label="ETH/USD")
    ax1.axhline(avg_price, color="#94a3b8", linewidth=1, linestyle="--", alpha=0.7, label=f"Avg ${avg_price:,.0f}")
    ax1.fill_between(times, band_lo, band_hi, alpha=0.1, color="#3b82f6", label="±5% band")
    ax1.set_ylabel("Price (USD)", color=TEXT)
    ax1.set_title("Live ETH/USD Price", color=TEXT)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"${x:,.0f}"))
    ax1.tick_params(colors=TEXT)
    ax1.legend(facecolor=DARK_BG, labelcolor=TEXT, fontsize=9)
    ax1.grid(alpha=0.3, color=GRID)
    for spine in ax1.spines.values():
        spine.set_edgecolor(GRID)

    # ── Donation USD Value ────────────────────────────────────────
    ax2.set_facecolor(DARK_BG)
    ax2.plot(times, usd_vals, color="#22c55e", linewidth=2, label=f"{donation_eth} ETH in USD")
    stable_val = usd_vals[0]  # Locked at first observation (stablecoin conversion)
    ax2.axhline(stable_val, color="#f97316", linewidth=2, linestyle="--",
                label=f"USDC locked at ${stable_val:.2f} (if converted immediately)")
    ax2.fill_between(times, min(usd_vals)*0.98, usd_vals,
                     where=[v < stable_val for v in usd_vals],
                     alpha=0.2, color="#ef4444", label="Loss vs USDC")
    ax2.fill_between(times, stable_val, usd_vals,
                     where=[v >= stable_val for v in usd_vals],
                     alpha=0.2, color="#22c55e", label="Gain vs USDC")
    ax2.set_ylabel("USD Value", color=TEXT)
    ax2.set_title(f"USD Value of {donation_eth} ETH Donation Over Time", color=TEXT)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"${x:,.2f}"))
    ax2.tick_params(colors=TEXT)
    ax2.legend(facecolor=DARK_BG, labelcolor=TEXT, fontsize=8)
    ax2.grid(alpha=0.3, color=GRID)
    for spine in ax2.spines.values():
        spine.set_edgecolor(GRID)

    plt.tight_layout()
    plt.savefig("price_feed_history.png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.show()
    print("\n✅ Chart saved to: price_feed_history.png")


# ─── MAIN: Live Polling Mode ─────────────────────────────────────

def run_live_tracker(num_beneficiaries: int = 5, iterations: int = 10):
    """
    Poll prices every POLL_INTERVAL_SECONDS for `iterations` rounds.
    Good for a demo / live presentation.
    """
    print("\n🚀 AllowanceCenter — Live Price Feed Tracker")
    print(f"   Polling every {POLL_INTERVAL_SECONDS}s for {iterations} iterations")
    print(f"   Simulating: {DONATION_ETH} ETH donation → {num_beneficiaries} refugees")
    print("   Press Ctrl+C to stop early\n")

    history = []

    try:
        for i in range(iterations):
            prices = get_crypto_prices()
            if prices:
                sim = simulate_donation(DONATION_ETH, prices["eth_usd"], num_beneficiaries)
                print_price_update(prices, sim)
                history.append(prices)

                # Save latest prices to JSON for other scripts to use
                with open("latest_prices.json", "w") as f:
                    json.dump({
                        "eth_usd": prices["eth_usd"],
                        "btc_usd": prices["btc_usd"],
                        "updated": prices["timestamp"].isoformat()
                    }, f, indent=2)

            if i < iterations - 1:
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n⛔ Stopped by user.")

    if history:
        plot_price_history(history, DONATION_ETH)


# ─── SINGLE CHECK MODE ────────────────────────────────────────────

def single_check(num_beneficiaries: int = 5):
    """Run once and show current prices + simulation."""
    prices = get_crypto_prices()
    if prices:
        sim = simulate_donation(DONATION_ETH, prices["eth_usd"], num_beneficiaries)
        print_price_update(prices, sim)
    else:
        print("Could not fetch prices. Check internet connection.")


if __name__ == "__main__":
    import sys

    if "--live" in sys.argv:
        # Run: python price_feed.py --live
        run_live_tracker(num_beneficiaries=5, iterations=20)
    else:
        # Default: single check
        single_check(num_beneficiaries=5)
        print("\nTip: Run with --live flag for continuous tracking:")
        print("     python price_feed.py --live")
