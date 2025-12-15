#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keep only FP2 as the "network" from exponent_yeo7_FP2.csv and export a sorted result.

Rules:
  - Kept columns: Subject, Day, Condition, Value, age, sex (if present)
  - Added/set:
      * label_7network: fixed to 'FP2'
      * MeasureID: fixed to 'FP2'
  - If multiple rows exist for the same (Subject, Day, Condition), Value is averaged.
  - Sorted by Subject, Day, then Condition order (1, 3, 4).
"""

import os
import pandas as pd

IN_CSV  = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/exponent_yeo7_FP2.csv"
OUT_CSV = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/exponent_yeo7_collapsed_FP2.csv"

COND_RANK = {1: 0, 3: 1, 4: 2}
NETWORK_NAME = "FP2"            # the only "network" kept
NETWORK_ORDER = [NETWORK_NAME]  # used for sorting

def main():
    df = pd.read_csv(IN_CSV)
    need = {"Subject", "Day", "Condition", "MeasureID", "Value"}
    miss = need - set(df.columns)
    if miss:
        raise ValueError(f"Missing required columns: {miss}")

    # Keep only FP2
    mask = df["MeasureID"].astype(str).str.upper().eq("FP2")
    df = df[mask].copy()
    if df.empty:
        raise ValueError("No records with MeasureID == 'FP2' were found in the input file.")

    # Standardize: fixed label and MeasureID
    df["label_7network"] = NETWORK_NAME
    df["MeasureID"] = NETWORK_NAME

    # Average duplicates within (Subject, Day, Condition, label_7network)
    grp_cols = ["Subject", "Day", "Condition", "label_7network"]
    agg = df.groupby(grp_cols, as_index=False).agg({"Value": "mean"})

    # Bring back covariates if present
    for col in ["age", "sex"]:
        if col in df.columns:
            extra = df.groupby(grp_cols, as_index=False).agg({col: "first"})
            agg = agg.merge(extra, on=grp_cols, how="left")

    # Sort: Subject, Day, then condition order 1->3->4
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

    # Quick validation: each (Subject, Day, FP2) should have Condition sequence [1,3,4]
    bad = 0
    for _, g in agg.groupby(["Subject", "Day", "label_7network"]):
        if g["Condition"].tolist() != [1, 3, 4]:
            bad += 1
    if bad == 0:
        print("[CHECK] Condition order is 1-3-4 for every (Subject, Day, FP2) ✅")
    else:
        print(f"[CHECK] {bad} groups are not in 1-3-4 order; likely missing data.")

if __name__ == "__main__":
    main()
