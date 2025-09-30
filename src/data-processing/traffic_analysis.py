#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traffic Analysis for Tai Lam vs NT Circular Road
------------------------------------------------
- Loads hk_tunnel_traffic.csv
- Computes Tai Lam share before/after toll change
- Compares peak vs off-peak (after policy change)
- Plots results
- Estimates revenue impact
"""

import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from config import (
    CACHE_FILE, POLICY_CHANGE_DATE,
    TOLL_BEFORE, TOLL_PEAK, TOLL_OFFPEAK
)


# -------------------------
# Load data
# -------------------------
print(f"📂 Loading {CACHE_FILE}...")
df = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"])

# Ensure Tai Lam and NT Circular exist
if not {"tai_lam", "nt_circular"}.issubset(df.columns):
    raise ValueError("CSV must contain 'tai_lam' and 'nt_circular' columns.")

# Drop rows without traffic
df = df.dropna(subset=["tai_lam", "nt_circular"]).copy()
df["total_traffic"] = df["tai_lam"] + df["nt_circular"]
df["tai_lam_share"] = df["tai_lam"] / df["total_traffic"]


# -------------------------
# Summary: Before vs After
# -------------------------
summary = df.groupby("period")["tai_lam_share"].mean()
print("\n🚦 Tai Lam Share Before vs After Policy Change")
print(summary)


# -------------------------
# Summary: Peak vs Off-peak (after only)
# -------------------------
after_df = df[df["period"] == "after"]
peak_summary = after_df.groupby("slot")["tai_lam_share"].mean()
print("\n⏰ Tai Lam Share (After Policy, Peak vs Off-peak)")
print(peak_summary)


# -------------------------
# Visualization
# -------------------------
plt.figure(figsize=(10,5))
df.set_index("timestamp").resample("D")["tai_lam_share"].mean().plot(label="Tai Lam Share")
plt.axvline(POLICY_CHANGE_DATE, color="red", linestyle="--", label="Policy Change (31 May 2025)")
plt.title("Tai Lam Tunnel Traffic Share Over Time")
plt.ylabel("Traffic Share (%)")
plt.legend()
plt.tight_layout()
plt.savefig("tai_lam_share_timeseries.png")
print("📊 Saved plot: tai_lam_share_timeseries.png")

summary.plot(kind="bar", title="Tai Lam Share: Before vs After", ylabel="Share (%)")
plt.tight_layout()
plt.savefig("tai_lam_share_before_after.png")
print("📊 Saved plot: tai_lam_share_before_after.png")

peak_summary.plot(kind="bar", title="Tai Lam Share: Peak vs Off-peak (After)", ylabel="Share (%)")
plt.tight_layout()
plt.savefig("tai_lam_share_peak_offpeak.png")
print("📊 Saved plot: tai_lam_share_peak_offpeak.png")


# -------------------------
# Revenue Estimation
# -------------------------
def toll_rate(row):
    if row["period"] == "before":
        return TOLL_BEFORE
    elif row["slot"] == "peak":
        return TOLL_PEAK
    elif row["slot"] == "offpeak":
        return TOLL_OFFPEAK
    return 0

df["toll"] = df.apply(toll_rate, axis=1)
df["revenue"] = df["tai_lam"] * df["toll"]

rev_summary = df.groupby("period")["revenue"].mean()
print("\n💰 Average Revenue per Hour (Tai Lam Tunnel)")
print(rev_summary)

# -------------------------
# Statistical Test
# -------------------------
print("\n📈 Regression Analysis (OLS)")
model = smf.ols("tai_lam_share ~ C(period) + C(slot)", data=df).fit()
print(model.summary())
