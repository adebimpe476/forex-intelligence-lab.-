"""All inputs are test fixtures; tests do not use a broker or execute orders."""
from decimal import Decimal
import pandas as pd
import pytest
from forexlab.risk import assess_risk, RiskPolicy, usd_direction
from forexlab.fx_sessions import session_bounds, session_bars
from forexlab.tickdata import validate_ticks


def plan(**kwargs):
    base = dict(signal_id="s001", pair="EURUSD", side="BUY", entry="1.1002", stop="1.0982",
                equity_usd="2000", day_start_equity_usd="2000")
    return assess_risk(**{**base, **kwargs})


def test_fractional_risk_lots_round_down_not_up():
    out = plan()
    assert out["status"] == "RESEARCH_SIZE_ONLY"
    assert out["lots"] == "0.04"  # budget 10 USD; model includes slippage and commission
    assert Decimal(out["risk_usd"]) <= Decimal("10")
    assert out["stop_distance_pips"] == "20"
    assert out["research_only"] and not out["execution_allowed"]


def test_jpy_risk_uses_usd_account_conversion_at_stop():
    x = plan(pair="USDJPY", side="BUY", entry="150.00", stop="149.50")
    assert x["status"] == "RESEARCH_SIZE_ONLY"
    assert x["stop_distance_pips"] == "50"
    assert Decimal(x["risk_usd"]) <= Decimal("10")
    assert x["usd_direction"] == 1
    assert usd_direction("EURUSD", "BUY") == -1
    assert usd_direction("GBPUSD", "SELL") == 1


def test_short_has_correct_stop_side():
    assert plan(side="SELL", entry="1.1000", stop="1.1020")["status"] == "RESEARCH_SIZE_ONLY"
    assert plan(side="SELL")["reason"] == "STOP_WRONG_SIDE"
    assert plan(stop="1.1002")["reason"] == "STOP_WRONG_SIDE"


def test_duplicate_signal_rejected():
    assert plan(seen_signal_ids={"s001"})["reason"] == "DUPLICATE_SIGNAL"


def test_correlation_rejected_with_two_same_usd_side_positions():
    out = plan(open_positions=[("EURUSD", "BUY"), ("USDJPY", "SELL")])
    assert out["reason"] == "CORRELATED_USD_DIRECTION_LIMIT"
    assert plan(open_positions=[("EURUSD", "BUY"), ("USDJPY", "BUY")])["status"] == "RESEARCH_SIZE_ONLY"


def test_portfolio_risk_and_daily_stop_blocks():
    assert plan(open_risk_usd="40")["reason"] == "PORTFOLIO_RISK_LIMIT"
    assert plan(day_realized_pnl_usd="-40")["reason"] == "DAILY_LOSS_LIMIT"
    assert plan(day_realized_pnl_usd="-39")["reason"] == "BELOW_MINIMUM_LOT_RISK_BUDGET"


def test_invalid_inputs_fail_closed_without_position():
    assert plan(entry="NaN")["status"] == "BLOCKED"
    assert plan(equity_usd="-1")["status"] == "BLOCKED"
    assert plan(pair="XAUUSD")["status"] == "BLOCKED"
    assert plan(account_currency="NGN")["status"] == "BLOCKED"
    assert plan(signal_id="")["status"] == "BLOCKED"
    assert plan(policy=RiskPolicy(risk_per_trade_fraction="1"))["status"] == "BLOCKED"
    assert plan(open_positions=[("BTCUSD", "BUY")])["status"] == "BLOCKED"


def test_policy_cannot_raise_risk_above_hard_caps():
    x = plan(policy=RiskPolicy(risk_per_trade_fraction="0.25"))
    assert x["status"] == "BLOCKED"
    x = plan(policy=RiskPolicy(max_daily_loss_fraction="0.5"))
    assert x["status"] == "BLOCKED"


def test_ny_rollover_is_21utc_in_summer_and_22utc_in_winter():
    summer = session_bounds("2026-07-10T21:00:00Z")
    winter = session_bounds("2026-01-10T22:00:00Z")
    assert summer["start_utc"] == pd.Timestamp("2026-07-10T21:00:00Z")
    assert winter["start_utc"] == pd.Timestamp("2026-01-10T22:00:00Z")
    assert session_bounds("2026-07-10T20:59:59Z")["start_utc"] == pd.Timestamp("2026-07-09T21:00:00Z")


def test_spring_h4_session_spans_3_real_utc_hours():
    b = session_bounds("2026-03-08T07:30:00Z", "H4")
    assert b["start_utc"] == pd.Timestamp("2026-03-08T06:00:00Z")
    assert b["end_utc"] == pd.Timestamp("2026-03-08T09:00:00Z")
    assert b["elapsed_utc_hours"] == 3


def test_fall_h4_session_spans_5_hours_including_both_0130():
    one = session_bounds("2026-11-01T05:30:00Z", "H4")
    two = session_bounds("2026-11-01T06:30:00Z", "H4")
    assert one["start_utc"] == two["start_utc"] == pd.Timestamp("2026-11-01T05:00:00Z")
    assert one["end_utc"] == two["end_utc"] == pd.Timestamp("2026-11-01T10:00:00Z")
    assert one["elapsed_utc_hours"] == 5


def test_session_bar_counts_real_ticks_no_interpolation():
    ticks = pd.DataFrame({"timestamp_utc":["2026-11-01T05:30:00Z", "2026-11-01T06:30:00Z", "2026-11-01T10:15:00Z"],
                          "bid":[150.,151.,152.],"ask":[150.02,151.02,152.02]})
    clean,_=validate_ticks(ticks)
    bars = session_bars(clean,"H4")
    assert len(bars)==2
    assert bars["tick_count"].tolist() == [2,1]
    assert bars["elapsed_utc_hours"].iloc[0] == 5
    assert bars["bid_close"].iloc[0] == 151
    assert bars["bar_end_utc"].iloc[0] == bars["bar_start_utc"].iloc[1]


def test_naive_clock_and_unsupported_tf_rejected():
    with pytest.raises(ValueError,match="timezone"):
        session_bounds("2026-10-09 21:00:00")
    with pytest.raises(ValueError,match="D1 and H4"):
        session_bounds("2026-10-09T21:00:00Z", "M15")


def test_unrealized_losses_reduce_remaining_day_budget():
    assert plan(day_unrealized_pnl_usd="-40")["reason"] == "DAILY_LOSS_LIMIT"
    assert plan(day_realized_pnl_usd="10", day_unrealized_pnl_usd="-50")["reason"] == "DAILY_LOSS_LIMIT"


def test_cli_research_size_is_nonexecuting(capsys):
    import json
    from forexlab.cli import main
    main(["research-size", "--signal-id", "demo-only", "--pair", "EURUSD",
          "--side", "BUY", "--entry", "1.1002", "--stop", "1.0982",
          "--equity-usd", "2000", "--day-start-equity-usd", "2000"])
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "RESEARCH_SIZE_ONLY"
    assert result["execution_allowed"] is False


def test_cli_session_bar_export_is_research_only(tmp_path, capsys):
    import json
    from forexlab.cli import main
    inp = tmp_path / "sample.csv"
    pd.DataFrame({"timestamp_utc":["2026-07-10T20:58:00Z", "2026-07-10T21:01:00Z"],
                  "bid":[1.1,1.2], "ask":[1.1002,1.2002]}).to_csv(inp,index=False)
    main(["session-bars", str(inp), "--timeframe", "D1", "--out", str(tmp_path / "out")])
    result = json.loads(capsys.readouterr().out)
    assert result["observed_bars"] == 2
    assert result["execution_allowed"] is False
    assert (tmp_path / "out" / "sample_D1_ny17_research.csv").exists()
