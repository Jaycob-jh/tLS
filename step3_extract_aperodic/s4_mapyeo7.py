#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collapse left/right (L/R) measures in exponent_yeo7.csv by averaging,
then sort by network priority and condition order (1, 3, 4).

Output:
  - exponent_yeo7_collapsed.csv

Kept columns:
  - Subject, Day, Condition, Value, age, sex (if present)

Added/renamed columns:
  - label_7network: 6 network names (Cont/Default/DorsAttn/SalVentAttn/SomMot/Vis)
  - MeasureID: generated from network code as 'Mean_<code>' (e.g., 'Mean_1')

Condition order per (Subject, Day, Network):
  - 1, then 3, then 4
"""

import os
import pandas as pd

IN_CSV  = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/exponent_yeo7.csv"
OUT_CSV = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/exponent_yeo7_collapsed.csv"

# Map side-specific base names to the final 6-network labels (after collapsing L/R)
SIDELESS_MAP = {
    "Control": "Cont",
    "DA": "DorsAttn",
    "Default": "Default",
    "SA": "SalVentAttn",
    "SM": "SomMot",
    "Visual": "Vis",
}

# Network code used to build MeasureID = Mean_<code>
NET_CODE = {
    "Default": 7,
    "SalVentAttn": 4,
    "Vis": 1,
    "SomMot": 2,
    "DorsAttn": 3,
    "Cont": 6,
}

# Sorting controls
NETWORK_ORDER = ["Cont", "Default", "DorsAttn", "SalVentAttn", "SomMot", "Vis"]
COND_RANK = {1: 0, 3: 1, 4: 2}


def main():
    df = pd.read_csv(IN_CSV)

    required = {"Subject", "Day", "Condition", "MeasureID", "Value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Remove _L/_R suffix to get the base network key (Control/DA/Default/SA/SM/Visual)
    base = df["MeasureID"].astype(str).str.replace(r"_L$|_R$", "", regex=True)
    df["net_raw"] = base

    # Map to the final 6-network label
    df["label_7network"] = df["net_raw"].map(SIDELESS_MAP)

    # Drop rows that cannot be mapped
    before = len(df)
    df = df[~df["label_7network"].isna()].copy()
    dropped = before - len(df)
    if dropped:
        print(f"[WARN] Dropped unmapped rows: {dropped}")

    # Collapse L/R: mean Value within (Subject, Day, Condition, label_7network)
    grp_cols = ["Subject", "Day", "Condition", "label_7network"]
    agg = df.groupby(grp_cols, as_index=False).agg({"Value": "mean"})

    # Bring back covariates if present (take first within group)
    for col in ["age", "sex"]:
        if col in df.columns:
            extra = df.groupby(grp_cols, as_index=False).agg({col: "first"})
            agg = agg.merge(extra, on=grp_cols, how="left")

    # Build MeasureID as Mean_<code>
    code_int = agg["label_7network"].map(NET_CODE)
    agg["MeasureID"] = "Mean_" + code_int.astype(int).astype(str)

    # Sort: Subject, Day, network order, then Condition order 1->3->4
    net_rank = {n: i for i, n in enumerate(NETWORK_ORDER)}
    agg["net_rank"]  = agg["label_7network"].map(net_rank).fillna(999).astype(int)
    agg["cond_rank"] = agg["Condition"].map(COND_RANK).fillna(99).astype(int)

    agg = (
        agg.sort_values(["Subject", "Day", "net_rank", "cond_rank"])
           .drop(columns=["net_rank", "cond_rank"])
           .reset_index(drop=True)
    )

    # Write output
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    agg.to_csv(OUT_CSV, index=False)
    print(f"[OK] Wrote: {OUT_CSV} (rows={len(agg)})")

    # Quick validation: each (Subject, Day, Network) should have Condition sequence [1,3,4]
    bad = 0
    for _, g in agg.groupby(["Subject", "Day", "label_7network"]):
        if g["Condition"].tolist() != [1, 3, 4]:
            bad += 1
    if bad == 0:
        print("[CHECK] Condition order is 1-3-4 for every (Subject, Day, Network) ✅")
    else:
        print(f"[CHECK] {bad} groups are not in 1-3-4 order; likely missing data.")


if __name__ == "__main__":
    main()
