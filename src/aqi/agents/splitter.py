"""Splitter (rule-based, locked). Time-ordered split; the test set is written once and hashed.

Only train/val paths go into the state. The test file lives in runs/<id>/locked/ and is read by the
Tester alone, after verifying the hash — no other agent can see test labels.
"""
from __future__ import annotations

import hashlib

import pandas as pd

from ..ledger import Ledger


def file_hash(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def assign(dates: pd.Series, split_cfg: dict) -> pd.Series:
    out = pd.Series(pd.NA, index=dates.index, dtype="object")
    for name in ("train", "val", "test"):
        lo, hi = split_cfg[name]
        out[dates.between(lo, hi)] = name
    return out


def run(state: dict, ledger: Ledger) -> dict:
    cfg = state["config"]["split"]
    f = pd.read_parquet(state["paths"]["features"])
    # A row belongs to a split only if both its issue day and its target day fall inside it,
    # so no target crosses a boundary.
    s_issue, s_target = assign(f["date"], cfg), assign(f["target_date"], cfg)
    f["split"] = s_issue.where(s_issue == s_target)
    sizes = f["split"].value_counts().to_dict()

    paths = dict(state["paths"])
    for name in ("train", "val"):
        p = ledger.dir / f"{name}.parquet"
        f[f.split == name].drop(columns="split").to_parquet(p, index=False)
        paths[name] = str(p)
    test_path = ledger.dir / "locked" / "test.parquet"
    f[f.split == "test"].drop(columns="split").to_parquet(test_path, index=False)
    digest = file_hash(test_path)

    ledger.log("splitter", "info", f"train {sizes.get('train', 0):,} / val {sizes.get('val', 0):,} / "
               f"test {sizes.get('test', 0):,} rows (test locked, sha256 {digest[:12]})",
               metrics={"sizes": sizes, "test_sha256": digest, "ranges": cfg})
    return {"paths": paths, "test_hash": digest}
