#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re
import pandas as pd

# ===== Paths (edit if needed) =====
IN_CSV  = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/offset_s100.csv"
IN_TSV  = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/atlas-4S156Parcels_dseg.tsv"
OUT_CSV = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/offsset_s100_labeled.csv"


def s100_to_label7network(s: str) -> str:
    """
    Convert S100-style labels to atlas-style 7Networks labels.

    Examples:
      'Cont_Cing_1 L' -> '7Networks_LH_Cont_Cing_1'
      'Vis_9 R'       -> '7Networks_RH_Vis_9'

    Notes:
      - If the input already starts with '7Networks_', return it unchanged.
      - If the input is not an S100 label (e.g., 'FP2'), return an empty string so it can be counted as unmatched.
    """
    if pd.isna(s):
        return ""
    s = str(s).strip()
    if s.startswith("7Networks_"):
        return s

    m = re.match(r"^(.+?)\s*([LR])$", s)
    if not m:
        return ""  # e.g., 'FP2' or any other non-matching label

    body = m.group(1).strip().replace(" ", "_")
    hemi = m.group(2).upper()
    hemi_tag = "LH" if hemi == "L" else "RH"
    return f"7Networks_{hemi_tag}_{body}"


def normalize_key(s: str) -> str:
    """
    Normalization used for joining keys:
      - lowercase
      - remove all whitespace
      - replace '-' with '_'
      - collapse repeated '_' characters
    This helps with robust matching between CSV/TSV label variations.
    """
    if pd.isna(s):
        return ""
    s2 = re.sub(r"\s+", "", str(s))
    s2 = s2.replace("-", "_")
    s2 = re.sub(r"_+", "_", s2)
    return s2.strip("_").lower()


def main():
    # 1) Read input files
    df = pd.read_csv(IN_CSV)
    ts = pd.read_csv(IN_TSV, sep="\t")

    # 2) Build label_7network from MeasureID
    #    Per your requirement: "rename" MeasureID to label_7network (i.e., drop MeasureID afterward).
    if "MeasureID" not in df.columns:
        raise ValueError("Input CSV is missing the 'MeasureID' column.")

    # Keep a copy of the original MeasureID for debugging (optional)
    df["s100_label"] = df["MeasureID"]

    df["MeasureID"] = df["MeasureID"].astype(str)
    df["label_7network"] = df["MeasureID"].apply(s100_to_label7network)
    df = df.drop(columns=["MeasureID"])  # strictly follow your stated steps

    # 3) Validate required columns in the atlas TSV
    required_cols = {"label_7network", "index", "network_label"}
    if not required_cols.issubset(ts.columns):
        missing = required_cols - set(ts.columns)
        raise ValueError(f"TSV is missing required columns: {missing}")

    # 4) Normalize join keys and merge
    df["__key__"] = df["label_7network"].map(normalize_key)
    ts["__key__"] = ts["label_7network"].map(normalize_key)

    atlas_keep = ts[["__key__", "index", "network_label"]].drop_duplicates("__key__")
    merged = df.merge(atlas_keep, on="__key__", how="left", validate="m:1")

    # 5) Add three columns:
    #    - MeasureID_int (nullable integer index)
    #    - MeasureID (formatted as Mean_<index>)
    #    - network_label (from atlas TSV)
    merged["MeasureID_int"] = merged["index"].astype("Int64")
    merged["MeasureID"] = merged["MeasureID_int"].map(lambda x: f"Mean_{int(x)}" if pd.notna(x) else "")

    # Place the new columns right after label_7network
    insert_at = list(merged.columns).index("label_7network") + 1
    for col in ["MeasureID", "MeasureID_int", "network_label"]:
        c = merged.pop(col)
        merged.insert(insert_at, col, c)
        insert_at += 1

    # 6) Report unmatched rows (where index is missing)
    miss = merged["MeasureID_int"].isna().sum()
    total = len(merged)
    if miss:
        examples = (
            merged.loc[merged["MeasureID_int"].isna(), "label_7network"]
            .dropna().astype(str).map(normalize_key).drop_duplicates().head(20).tolist()
        )
        print(f"[WARN] Unmatched rows: {miss}/{total}. Example normalized keys: {examples}")

    # 7) Write output
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    merged.to_csv(OUT_CSV, index=False)
    print(f"[OK] Wrote: {OUT_CSV}")


if __name__ == "__main__":
    main()
