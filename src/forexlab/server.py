"""Read-only research dashboard. No broker credentials or order routes."""
from pathlib import Path
import csv
from fastapi import FastAPI
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / 'data/raw/fred_h10_daily_snapshot_2026-10-08.csv'
WEB = ROOT / 'web/index.html'
app = FastAPI(title='Forex Intelligence Lab — Research Only', version='0.1.0')


@app.get('/')
def home():
    return FileResponse(WEB)


@app.get('/api/health')
def health():
    return {"status": "ok", "mode": "RESEARCH_ONLY", "broker_connected": False,
            "order_execution_enabled": False, "ai_trained": False, "validated_strategy_count": 0}


@app.get('/api/overview')
def overview():
    return {"phase": "Source audit + experimental baselines",
            "pairs": ["EURUSD", "USDJPY", "GBPUSD"],
            "timeframes_requested": ["M15", "M30", "H1", "H4", "D1"],
            "available_source_timeframe": "D1 indicative fixing; no intraday OHLC",
            "full_history_audit": {"start": "1999-01-04", "end": "2026-10-02", "valid_daily_observations_per_pair": 6960},
            "locally_archived": {"start": "2026-09-01", "end": "2026-10-02", "rows": 24,
                                 "note": "A small verifiable snapshot, NOT the complete history"},
            "broker": "NOT CONNECTED", "live_data": False, "orders_enabled": False,
            "signal": "WAIT", "signal_reason": "No validated strategy, live feed or execution adapter",
            "win_rate": None, "historical_performance": None,
            "strategies": [{"name":"Trend following","state":"hypothesis"},
                           {"name":"Breakout","state":"hypothesis"},
                           {"name":"Mean reversion","state":"hypothesis"}]}


@app.get('/api/history')
def history():
    with HISTORY.open(newline='') as f:
        rows = list(csv.DictReader(f))
    # Empty original FRED observations remain null; never fabricate/fill prices.
    return {"source":"FRB H.10 via FRED", "source_type":"daily indicative NY noon observations",
            "as_of":"2026-10-08", "is_live":False,
            "series":[{"date":r['date'],**{p:(float(r[p]) if r[p] else None)
                    for p in ('EURUSD','USDJPY','GBPUSD')}} for r in rows]}
