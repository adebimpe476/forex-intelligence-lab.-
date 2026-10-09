"""Purged chronological window plan; does NOT claim out-of-sample performance.

This planner prevents row-overlap when *future-label horizons* are known. It
never reuses test windows in training, does not fit models or inspect labels,
and reserves a permanently locked final holdout until a pre-registered review.
"""
from __future__ import annotations

import hashlib
import json

import pandas as pd


def plan_walkforward(timestamps: pd.Series | pd.DatetimeIndex,
                     *, min_train: int = 300, test_size: int = 60,
                     embargo: int = 5, label_horizon: int = 1,
                     final_holdout: int = 100) -> dict:
    if any(isinstance(v, bool) or not isinstance(v, int) for v in
           (min_train, test_size, embargo, label_horizon, final_holdout)):
        raise ValueError("All split parameters must be integers")
    if min_train < 10 or test_size < 1 or embargo < label_horizon or label_horizon < 1 or final_holdout < 1:
        raise ValueError("Need min_train>=10, test_size>=1, embargo>=label_horizon>=1 and holdout>=1")
    idx = pd.DatetimeIndex(timestamps)
    if idx.tz is None or idx.hasnans or not idx.is_monotonic_increasing or idx.has_duplicates:
        raise ValueError("Data must have strictly increasing timezone-aware timestamps")
    if len(idx) < min_train + embargo + test_size + final_holdout:
        raise ValueError("Insufficient observations for one complete fold and locked holdout")
    locked_start = len(idx) - final_holdout
    folds = []
    # Expanding training prefix + embargo + unseen next test; no training on
    # future test rows for a given fold, and no test touches final holdout.
    test_begin = min_train + embargo
    while test_begin + test_size <= locked_start:
        train_end = test_begin - embargo
        test_end = test_begin + test_size
        folds.append({"fold":len(folds)+1,
                      "train_range_row_exclusive":[0,train_end],
                      "embargo_range_row_exclusive":[train_end,test_begin],
                      "test_range_row_exclusive":[test_begin,test_end],
                      "train_last_utc":idx[train_end-1].isoformat(),
                      "test_first_utc":idx[test_begin].isoformat(),
                      "test_last_utc":idx[test_end-1].isoformat()})
        test_begin = test_end
    if not folds:
        raise ValueError("No complete walk-forward folds")
    footprint = hashlib.sha256("\n".join(x.isoformat() for x in idx).encode()).hexdigest()
    p = {"data_timestamp_sha256":footprint,"observations":len(idx),"min_train":min_train,
         "test_size":test_size,"embargo":embargo,"label_horizon":label_horizon,
         "final_holdout_rows":final_holdout,
         "locked_final_holdout_range_row_exclusive":[locked_start,len(idx)],
         "folds":folds,"holdout_untouched":True,"out_of_sample_verified":False,
         "execution_allowed":False,
         "warning":"Split plan only. Results become contaminated if experiment choices use test windows repeatedly."}
    p["plan_sha256"] = hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return p
