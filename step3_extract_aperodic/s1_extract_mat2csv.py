#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
RULES / CONTRACT (ENGLISH)
1) Purpose
   Batch-export Brainstorm specparam(FOOOF) results from .mat files to CSV.

2) Inputs
   - IN_GLOB must match Brainstorm outputs like:
       .../data/sub*/@rawsub*_t*_resample_band_notch_interpbad/timefreq_psd_*_specparam.mat
   - Each .mat is expected to contain:
       Options.FOOOF.aperiodics with fields: channel, offset, exponent

3) Output
   - CSV is written to:
       OUT_ROOT/<subj>/<subj>_<RUN>_<Comment>.csv
   - <RUN> extraction priority:
       (a) filename: timefreq_psd_<RUN>_specparam.mat  (supports t1, t01, t1t3t5; preserves digits)
       (b) directory: @rawsub*_t*_resample_band_notch_interpbad (same RUN format)
       (c) fallback: first occurrence of (t\d+(?:t\d+)*) from any available metadata/path
   - <subj> extraction priority:
       (a) path segment: /data/<subj>/
       (b) fallback: first occurrence of sub* from any available metadata/path
   - <Comment>:
       prefer .mat variable "Comment"; if empty, use "specparam"
       filename is sanitized to [A-Za-z0-9_.+-] with others replaced by "-"

4) Robustness / Fallbacks
   - If SciPy cannot read the .mat (e.g., v7.3 HDF5), falls back to mat73 (optional).
   - If HeadModelFile/Comment are empty, subject and RUN are still derived from the .mat path.

5) Dependencies
   - Required: numpy, pandas, scipy
   - Optional: mat73 (only for MATLAB v7.3 HDF5 .mat)

6) Failure policy
   - Per-file failure does not stop the batch; errors are logged to stdout.
=============================================================================
"""

import os
import re
import glob
from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

# --------- Config ---------
IN_GLOB = (
    "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/dataset/brainstorm_db/"
    "1064@FP2_rtLS-EEG/data/sub*/@rawsub*_t*_resample_band_notch_interpbad/"
    "timefreq_psd_*_specparam.mat"
)
OUT_ROOT = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/FOOOF_new"
# --------------------------


# ---------- MAT loader (SciPy first; mat73 fallback for v7.3) ----------
def load_mat_any(path: str) -> Dict[str, Any]:
    try:
        from scipy.io import loadmat, matlab

        def to_native(obj: Any) -> Any:
            if isinstance(obj, matlab.mio5_params.mat_struct):
                return {fn: to_native(getattr(obj, fn)) for fn in obj._fieldnames}
            if isinstance(obj, np.ndarray) and obj.dtype == object:
                # keep structure but unwrap object arrays
                return [to_native(x) for x in obj.squeeze().tolist()]
            return obj

        raw = loadmat(path, squeeze_me=True, struct_as_record=False)
        return {k: to_native(v) for k, v in raw.items() if not k.startswith("__")}
    except Exception:
        try:
            import mat73  # type: ignore
            return mat73.loadmat(path)
        except Exception as e:
            raise RuntimeError(f"Failed to read {path}: {e}") from e


# --------------------- Helpers ---------------------
_RUN_RE = re.compile(r"(t\d+(?:t\d+)*)")
_FILE_RUN_RE = re.compile(r"timefreq_psd_(t\d+(?:t\d+)*)_specparam\.mat$")
_DIR_RUN_RE = re.compile(r"/@rawsub[^/]*_(t\d+(?:t\d+)*)_resample_band_notch_interpbad/")

def is_empty(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, str):
        s = x.strip()
        return s == "" or s in ("[]", "nan", "NaN")
    if isinstance(x, (list, tuple, np.ndarray)):
        try:
            return len(x) == 0
        except Exception:
            return False
    return False


def as_path_posix(p: str) -> str:
    return p.replace("\\", "/")


def clean_filename(s: Any) -> str:
    s = str(s)
    s = re.sub(r"[^A-Za-z0-9_.+\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "specparam"


def unwrap_singleton_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Some exporters nest everything under one top-level variable; unwrap it."""
    if "Options" not in d and len(d) == 1 and isinstance(next(iter(d.values())), dict):
        return next(iter(d.values()))
    return d


def run_from_filename(mat_path: str) -> Optional[str]:
    base = os.path.basename(mat_path)
    m = _FILE_RUN_RE.search(base)
    return m.group(1) if m else None


def run_from_dir(mat_path: str) -> Optional[str]:
    p = as_path_posix(mat_path)
    m = _DIR_RUN_RE.search(p)
    if m:
        return m.group(1)
    # relaxed fallbacks (keep your original idea but simpler)
    m = re.search(r"/@rawsub[^/]*_(t\d+(?:t\d+)*)_resample", p)
    if m:
        return m.group(1)
    m = re.search(r"_(t\d+(?:t\d+)*)_", p)
    return m.group(1) if m else None


def subj_from_matpath(mat_path: str) -> Optional[str]:
    p = as_path_posix(mat_path)
    m = re.search(r"/data/(sub[^/]+)/", p)
    if m:
        return m.group(1)
    m = re.search(r"/(sub\d+)(/|_)", p)
    return m.group(1) if m else None


def find_subj_run(d: Dict[str, Any], mat_path: str) -> Tuple[str, str]:
    """Return (subj, run) with priority rules described in the header."""
    run = run_from_filename(mat_path) or run_from_dir(mat_path)
    subj = subj_from_matpath(mat_path)

    if subj is not None and run is not None:
        return subj, run

    # metadata candidates (keep your fallback behavior)
    dd = unwrap_singleton_dict(d)
    cands: List[str] = [mat_path]
    for key in ("HeadModelFile", "DataFile", "SurfaceFile"):
        v = dd.get(key)
        if not is_empty(v):
            cands.append(str(v))

    if subj is None:
        for s in cands:
            s = as_path_posix(s)
            m = re.search(r"/data/(sub[^/]+)/", s) or re.search(r"/(sub\d+)(/|_)", s)
            if m:
                subj = m.group(1)
                break

    if run is None:
        for s in cands:
            m = _RUN_RE.search(str(s))
            if m:
                run = m.group(1)
                break

    return (subj or "unknown"), (run or "tX")


def make_basename(d: Dict[str, Any], mat_path: str) -> Tuple[str, str]:
    """Return (subj, base) where base is: subj_RUN_comment"""
    dd = unwrap_singleton_dict(d)
    comment = dd.get("Comment")
    subj, run = find_subj_run(d, mat_path)
    comment_clean = "specparam" if is_empty(comment) else clean_filename(comment)
    return subj, f"{subj}_{run}_{comment_clean}"


def to_float(x: Any) -> float:
    try:
        if isinstance(x, (np.ndarray, list, tuple)):
            arr = np.array(x).squeeze()
            if arr.size == 0:
                return np.nan
            if arr.size == 1:
                return float(arr.item())
            # if multiple values, take first (rare for these fields)
            return float(arr.flat[0])
        return float(x)
    except Exception:
        return np.nan


def to_int_or_nan(x: Any) -> float:
    # keep as float/NaN first; later we cast to pandas Int64 where possible
    v = to_float(x)
    try:
        return np.nan if np.isnan(v) else int(v)
    except Exception:
        return np.nan


def get_aperiodics(d: Dict[str, Any]) -> pd.DataFrame:
    dd = unwrap_singleton_dict(d)
    options = dd.get("Options")
    if options is None:
        raise KeyError("Missing variable: Options")
    fooof = options.get("FOOOF") if isinstance(options, dict) else getattr(options, "FOOOF", None)
    if fooof is None:
        raise KeyError("Missing variable: Options.FOOOF (not a specparam export?)")
    ap = fooof.get("aperiodics") if isinstance(fooof, dict) else getattr(fooof, "aperiodics", None)
    if ap is None:
        raise KeyError("Missing variable: Options.FOOOF.aperiodics")

    rows: List[Dict[str, Any]] = []

    # Case A: dict-of-arrays
    if isinstance(ap, dict):
        ch = np.asarray(ap.get("channel", []))
        off = np.asarray(ap.get("offset", []))
        exp = np.asarray(ap.get("exponent", []))
        n = max(len(ch), len(off), len(exp)) if (len(ch) or len(off) or len(exp)) else 0
        for i in range(n):
            rows.append(
                {
                    "channel": to_int_or_nan(ch[i]) if i < len(ch) else np.nan,
                    "offset": to_float(off[i]) if i < len(off) else np.nan,
                    "exponent": to_float(exp[i]) if i < len(exp) else np.nan,
                }
            )
    else:
        # Case B: array of structs / objects
        flat = np.ravel(ap)
        for it in flat:
            if isinstance(it, dict):
                ch, off, exp = it.get("channel"), it.get("offset"), it.get("exponent")
            else:
                ch = getattr(it, "channel", np.nan)
                off = getattr(it, "offset", np.nan)
                exp = getattr(it, "exponent", np.nan)
            rows.append({"channel": to_int_or_nan(ch), "offset": to_float(off), "exponent": to_float(exp)})

    df = pd.DataFrame(rows, columns=["channel", "offset", "exponent"])
    # best-effort nullable integer channel
    try:
        df["channel"] = df["channel"].astype("Int64")
    except Exception:
        pass
    return df


# ----------------------- Main -----------------------
def main() -> None:
    files = sorted(glob.glob(IN_GLOB))
    if not files:
        print(f"[WARN] No files matched: {IN_GLOB}")
        return

    os.makedirs(OUT_ROOT, exist_ok=True)

    for f in files:
        try:
            d = load_mat_any(f)
            subj, base = make_basename(d, f)
            out_dir = os.path.join(OUT_ROOT, subj)
            os.makedirs(out_dir, exist_ok=True)

            df = get_aperiodics(d)
            out_csv = os.path.join(out_dir, base + ".csv")
            df.to_csv(out_csv, index=False)

            print(f"[OK] {f} -> {out_csv} (rows={len(df)})")
        except Exception as e:
            print(f"[FAIL] {f}\n       {e}")


if __name__ == "__main__":
    main()
