#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append age/sex from /results/eeg_exp.csv to:
  - /results/offset_yeo7_FP2.csv
  - /results/exponent_yeo7_FP2.csv

Rules:
  * Merge by Subject (normalize IDs like 'sub1', '001' -> integer 1).
  * Preserve the original row order and original column order; only append 'age','sex' at the end.
  * If a Subject has no match in eeg_exp.csv, age/sex stays empty (NaN).
"""

import os
import re
import pandas as pd

# -------- Paths (edit if needed) --------
ROOT = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results"
PATH_META = os.path.join(ROOT, "eeg_exp.csv")
PATH_OFF  = os.path.join(ROOT, "offset_yeo7_FP2.csv")
PATH_EXP  = os.path.join(ROOT, "exponent_yeo7_FP2.csv")
# ---------------------------------------

def canonical_subject(x):
    """Normalize 'sub12' / '012' / 12 -> 12 (int). Return None if not parseable."""
    if pd.isna(x):
        return None
    s = str(x)
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None

def load_meta(path):
    """Read eeg_exp.csv, standardize column names, and return unique Subject -> (age, sex)."""
    m = pd.read_csv(path)
    m.columns = [c.strip().lower() for c in m.columns]

    # Flexible column mapping: subject, age, sex/gender
    col_sub = next((c for c in m.columns if c in ("subject", "subj", "id", "participant")), None)
    if col_sub is None:
        raise ValueError("No Subject column found in eeg_exp.csv (accepted: subject/subj/id/participant)")
    col_age = next((c for c in m.columns if c in ("age", "ages")), None)
    col_sex = next((c for c in m.columns if c in ("sex", "gender")), None)
    if col_age is None or col_sex is None:
        raise ValueError("Missing age or sex/gender column in eeg_exp.csv")

    m = m[[col_sub, col_age, col_sex]].copy()
    m.rename(columns={col_sub: "Subject", col_age: "age", col_sex: "sex"}, inplace=True)
    m["Subject"] = m["Subject"].map(canonical_subject)

    # Keep the first record per Subject
    m = (m.sort_values(["Subject"])
          .dropna(subset=["Subject"])
          .groupby("Subject", as_index=False)
          .agg({"age": "first", "sex": "first"}))
    return m

def append_meta(in_path, meta_df, out_path=None):
    """
    Append meta_df age/sex to the CSV at in_path by merging on Subject.
    Writes back to out_path (defaults to overwrite in_path).
    """
    df = pd.read_csv(in_path)
    original_cols = df.columns.tolist()

    if "Subject" not in df.columns:
        raise ValueError(f"No 'Subject' column found in {os.path.basename(in_path)}")

    df = df.copy()
    df["Subject"] = df["Subject"].map(canonical_subject)

    merged = df.merge(meta_df, on="Subject", how="left", sort=False)

    # Final column order: original columns (without existing age/sex) + appended age/sex
    for c in ("age", "sex"):
        if c in original_cols:
            original_cols.remove(c)
    final_cols = original_cols + ["age", "sex"]
    merged = merged.reindex(columns=final_cols)

    out_path = out_path or in_path
    merged.to_csv(out_path, index=False)
    print(f"[OK] Appended: {out_path} (rows={len(merged)})")

def main():
    meta = load_meta(PATH_META)
    append_meta(PATH_OFF, meta)
    append_meta(PATH_EXP, meta)

if __name__ == "__main__":
    main()
