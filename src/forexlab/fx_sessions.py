"""New York 17:00 FX research-session boundaries, including US DST transitions.

Provider/broker daily candle boundaries vary; use only with explicitly selected
17:00 America/New_York research convention. Observed tick bars only. No orders.
"""
from __future__ import annotations

from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd

NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def _utc(ts: object) -> datetime:
    x = pd.Timestamp(ts)
    if x.tzinfo is None or pd.isna(x):
        raise ValueError("Timestamp must be timezone-aware")
    return x.tz_convert("UTC").to_pydatetime()


def session_bounds(ts: object, timeframe: str = "D1") -> dict:
    """Return UTC start/end of NY-17:00-anchored D1 or H4 session containing ts.

    H4 is defined on the *New York wall clock* at 17,21,01,05,09,13.
    Around DST jumps, some H4 blocks span 3 or 5 elapsed UTC hours.
    At fall-back, both instances of 01:XX belong to the 01:00 block,
    anchored at the first 01:00 (fold=0).
    """
    if timeframe not in ("D1", "H4"):
        raise ValueError("Only D1 and H4 New York session boundaries are supported")
    utc_ts = _utc(ts)
    local = utc_ts.astimezone(NY)
    current_date = local.date()
    if local.hour < 17:
        current_date -= timedelta(days=1)
    base = datetime.combine(current_date, time(17, 0))
    if timeframe == "D1":
        start_wall, end_wall = base, base + timedelta(days=1)
    else:
        wall_elapsed = local.replace(tzinfo=None) - base
        bucket = int(wall_elapsed.total_seconds() // (4 * 3600))
        start_wall = base + timedelta(hours=4 * bucket)
        end_wall = start_wall + timedelta(hours=4)
    # NY local 17:00 is never ambiguous; 01:00 DST fall-back can be, fold=0.
    start = start_wall.replace(tzinfo=NY, fold=0).astimezone(UTC)
    end = end_wall.replace(tzinfo=NY, fold=0).astimezone(UTC)
    if not start <= utc_ts < end:
        raise ValueError("Internal session boundary calculation failed")
    return {"timeframe": timeframe, "session_date_ny": str(current_date),
            "start_utc": pd.Timestamp(start), "end_utc": pd.Timestamp(end),
            "elapsed_utc_hours": (end - start).total_seconds() / 3600.0,
            "convention": "17:00 America/New_York (not automatic broker calendar)"}


def session_bars(validated_ticks: pd.DataFrame, timeframe: str = "D1") -> pd.DataFrame:
    """Build observed only session bars; never fill unavailable quote windows."""
    needed = {"timestamp_utc", "bid", "ask", "mid", "spread"}
    if not needed.issubset(validated_ticks.columns):
        raise ValueError("Must use cleaned output of tickdata.validate_ticks")
    if validated_ticks.empty:
        raise ValueError("No ticks supplied")
    x = validated_ticks.copy()
    x["timestamp_utc"] = pd.to_datetime(x["timestamp_utc"], utc=True, errors="raise")
    if not x["timestamp_utc"].is_monotonic_increasing or x["timestamp_utc"].isna().any():
        raise ValueError("Unordered or invalid ticks")
    # Include source output only if it passed the canonical validator again.
    from .tickdata import validate_ticks
    validated, _ = validate_ticks(x[["timestamp_utc", "bid", "ask"]].assign(
        timestamp_utc=x["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")))
    # Retain original validated tick timestamps, strictly no interpolation.
    bounds = [session_bounds(t, timeframe) for t in validated["timestamp_utc"]]
    validated["start"] = [b["start_utc"] for b in bounds]
    validated["end"] = [b["end_utc"] for b in bounds]
    rows = []
    for (start, end), grp in validated.groupby(["start", "end"], sort=True):
        row = {"bar_start_utc": start, "bar_end_utc": end,
               "elapsed_utc_hours": (end - start).total_seconds()/3600.0,
               "tick_count": int(len(grp)), "session_date_ny": session_bounds(grp["timestamp_utc"].iloc[0], timeframe)["session_date_ny"]}
        for side in ("bid", "ask", "mid"):
            z = grp[side]
            row.update({f"{side}_open":float(z.iloc[0]), f"{side}_high":float(z.max()),
                        f"{side}_low":float(z.min()), f"{side}_close":float(z.iloc[-1])})
        row.update(spread_mean=float(grp["spread"].mean()), spread_max=float(grp["spread"].max()), spread_last=float(grp["spread"].iloc[-1]))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("bar_start_utc").reset_index(drop=True)
