# Reddit Post Draft — r/solana (also post to r/defi, r/algotrading)

---

**Title:**
I built a DeFi liquidation risk monitor using Pyth's confidence intervals (the
signal nobody else is using)

---

**Body:**

Most DeFi users get liquidated not because they weren't watching prices —
but because they had no early warning.

I built **PythGuard**: a real-time risk monitor for Solana lending positions
on Marginfi and Kamino. The interesting part is *how* it detects risk before
it becomes a liquidation.

**The insight nobody uses:**

Every Pyth price feed publishes two values:
```
price:      $136.40   ← what everyone reads
confidence: ± $0.12   ← what PythGuard reads
```

The confidence interval is how certain Pyth's oracle is about the price.
When it *widens*, the market is unstable — this often happens *before* the
price drops. PythGuard uses this as the primary risk signal.

Interestingly, Marginfi itself uses confidence intervals internally when
calculating liquidation thresholds (they use the bottom of the 95% confidence
band). PythGuard just surfaces that same signal to you as the user.

**How it works:**

1. Connect your Phantom wallet
2. PythGuard scans your open positions on Marginfi/Kamino
3. Computes a Risk Score (0–100) using:
   - Collateral ratio vs liquidation threshold (40%)
   - Pyth confidence interval right now (40%)
   - Confidence ratio trend over last 30 minutes (20%)
4. Alerts you when score crosses HIGH (75+)

**Tech stack:** Rust (Solana reader), Python FastAPI (risk engine + Pyth Pro
MCP client), React dashboard.

Demo works without a wallet — the dashboard starts in demo mode showing
3 simulated positions with live-updating data.

GitHub: https://github.com/your-handle/pythguard (Apache 2.0)
Live demo: https://pythguard.your-deployment.com

Happy to answer questions about the Pyth integration or the risk model.

---

**Tags to use on Reddit:**
- r/solana
- r/defi
- r/algotrading (frame it around the confidence signal)
- r/CryptoCurrency

**Tip for upvotes:** Post at 9am EST on a weekday. Reply to every comment
within the first hour — Reddit's algorithm rewards early engagement.
