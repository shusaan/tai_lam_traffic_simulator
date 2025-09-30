#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traffic Analysis for Tai Lam AI Traffic Optimizer
------------------------------------------------
Integrated with the main project for ML model training

- Loads processed Hong Kong traffic data
- Analyzes traffic patterns and toll policy impact
- Generates features for ML model training
- Exports training datasets
- Creates visualization reports

Usage:
    python src/data-processing/traffic_analysis.py
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import statsmodels.formula.api as smf
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logging.warning("statsmodels not available, skipping regression analysis")

from config import (
    CACHE_FILE, OUTPUT_DIR, POLICY_CHANGE_DATE,
    TOLL_BEFORE, TOLL_PEAK, TOLL_OFFPEAK,
    BASE_TOLL, MIN_TOLL, MAX_TOLL
)

# Setup logging
logging.basicConfig(level=logging.INFO)


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
# Feature Engineering for ML
# -------------------------
def create_ml_features(df):
    """Create features for ML model training"""
    ml_df = df.copy()
    
    # Time-based features
    ml_df['hour'] = ml_df['timestamp'].dt.hour
    ml_df['day_of_week'] = ml_df['timestamp'].dt.dayofweek
    ml_df['is_weekend'] = ml_df['day_of_week'].isin([5, 6]).astype(int)
    
    # Traffic features
    traffic_cols = ['tai_lam_tunnel', 'tuen_mun_road', 'nt_circular_road']
    available_cols = [col for col in traffic_cols if col in ml_df.columns]
    
    if not available_cols:
        # Try alternative column names
        if 'tai_lam' in ml_df.columns:
            ml_df['tai_lam_tunnel'] = ml_df['tai_lam']
        if 'nt_circular' in ml_df.columns:
            ml_df['nt_circular_road'] = ml_df['nt_circular']
        available_cols = [col for col in traffic_cols if col in ml_df.columns]
    
    if available_cols:
        ml_df['total_traffic'] = ml_df[available_cols].sum(axis=1)
        if 'tai_lam_tunnel' in ml_df.columns:
            ml_df['tai_lam_share'] = ml_df['tai_lam_tunnel'] / (ml_df['total_traffic'] + 1)
    
    # Policy features
    ml_df['is_after_policy'] = (ml_df['timestamp'] >= POLICY_CHANGE_DATE).astype(int)
    ml_df['is_peak'] = ml_df.get('slot', 'na').eq('peak').astype(int)
    
    return ml_df


# -------------------------
# Export ML Training Data
# -------------------------
def export_ml_training_data(ml_df):
    """Export processed data for ML model training"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Export training data
    training_file = os.path.join(OUTPUT_DIR, 'ml_training_data.csv')
    ml_df.to_csv(training_file, index=False)
    
    logging.info(f"✅ ML training data exported: {training_file}")
    return training_file


# -------------------------
# Enhanced Main Function
# -------------------------
def main():
    """Main analysis pipeline"""
    logging.info("🚀 Starting Traffic Analysis Pipeline")
    
    try:
        # Load and validate data
        if not os.path.exists(CACHE_FILE):
            logging.error(f"❌ Data file not found: {CACHE_FILE}")
            logging.info("Run hk_traffic.py first to generate the data")
            return
        
        logging.info(f"📂 Loading {CACHE_FILE}...")
        df = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"])
        
        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Handle different column names
        if 'tai_lam' in df.columns and 'tai_lam_tunnel' not in df.columns:
            df['tai_lam_tunnel'] = df['tai_lam']
        if 'nt_circular' in df.columns and 'nt_circular_road' not in df.columns:
            df['nt_circular_road'] = df['nt_circular']
        
        # Basic analysis
        if 'tai_lam_tunnel' in df.columns:
            traffic_cols = [col for col in ['tai_lam_tunnel', 'tuen_mun_road', 'nt_circular_road'] if col in df.columns]
            df = df.dropna(subset=traffic_cols).copy()
            df["total_traffic"] = df[traffic_cols].sum(axis=1)
            df["tai_lam_share"] = df["tai_lam_tunnel"] / df["total_traffic"]
            
            # Analysis by period
            if 'period' in df.columns:
                summary = df.groupby("period")["tai_lam_share"].mean()
                print("\n🚦 Tai Lam Share Before vs After Policy Change")
                print(summary)
        
        # Create ML features and export
        ml_df = create_ml_features(df)
        training_file = export_ml_training_data(ml_df)
        
        # Statistical analysis if available
        if STATSMODELS_AVAILABLE and 'period' in df.columns and 'slot' in df.columns:
            try:
                model = smf.ols("tai_lam_share ~ C(period) + C(slot)", data=df).fit()
                print("\n📈 Regression Analysis (OLS)")
                print(model.summary())
            except Exception as e:
                logging.warning(f"Regression analysis failed: {str(e)}")
        
        logging.info("\n✅ Analysis Complete!")
        logging.info(f"   - Training data: {training_file}")
        
    except Exception as e:
        logging.error(f"❌ Analysis failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
