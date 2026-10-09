"""Fail-closed inspection of prerequisites for building/running open-source LEAN.

This check DOES NOT install, run, certify, or impersonate QuantConnect LEAN.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess


def _get_version(program: str, args: list[str]) -> str | None:
    if not shutil.which(program):
        return None
    try:
        proc = subprocess.run([program, *args], capture_output=True, text=True,
                              timeout=7, check=False)
        if proc.returncode != 0:
            return None
        return proc.stdout.strip().splitlines()[0][:180]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def inspect_lean_environment(*, data_manifest: str | None = None) -> dict:
    """Return missing actions; no run or validated backtest until captured separately."""
    dotnet = _get_version("dotnet", ["--version"])
    docker = _get_version("docker", ["--version"])
    git = _get_version("git", ["--version"])
    missing=[]
    if dotnet is None and docker is None:
        missing.append("DOTNET_OR_DOCKER_NOT_AVAILABLE")
    if git is None:
        missing.append("GIT_NOT_AVAILABLE")
    if not data_manifest:
        missing.append("NO_DATA_PROVENANCE_MANIFEST")
    elif not Path(data_manifest).is_file():
        missing.append("DATA_MANIFEST_NOT_FOUND")
    else:
        try:
            meta=json.loads(Path(data_manifest).read_text(encoding="utf-8"))
            if not isinstance(meta, dict) or not meta.get("source_sha256"):
                missing.append("DATA_HASH_OR_MANIFEST_MISSING")
            if not (meta.get("provenance_verified_externally") and meta.get("licensed_rights_verified_externally")):
                missing.append("MANUAL_SOURCE_AND_RIGHTS_VERIFICATION_PENDING")
        except (OSError, ValueError, TypeError):
            missing.append("INVALID_DATA_MANIFEST")
    return {"dotnet_version":dotnet, "docker_version":docker,
            "git_version":git, "prerequisite_blockers":missing,
            "lean_engine_installed_verified":False,
            "lean_backtest_executed":False,
            "lean_results_verified":False,
            "execution_allowed":False,
            "next":"Build QuantConnect/Lean from pinned source or use a permitted Docker deployment; load rights-cleared bid/ask data, then execute and reconcile a no-order ingestion smoke test."}
