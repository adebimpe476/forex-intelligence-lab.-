"""Cost preflight only: no network and no paid API in tests."""
import pytest

from scripts.check_databento_historical_cost import estimate_costs


class FakeMetadata:
    def __init__(self):
        self.calls = []

    def get_dataset_range(self, **kwargs):
        assert kwargs["dataset"] == "GLBX.MDP3"
        return {"start": "2017-05-01T00:00:00Z", "end": "2026-10-10T00:00:00Z"}

    def get_cost(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["dataset"] == "GLBX.MDP3"
        assert kwargs["stype_in"] == "continuous"
        return {"trades": 1.25, "mbp-10": 4.5, "mbo": 7.0}[kwargs["schema"]]


class FakeClient:
    def __init__(self):
        self.metadata = FakeMetadata()

    @property
    def timeseries(self):
        raise AssertionError("Market-data downloads must NEVER occur in preflight")


def test_cost_only_metadata_no_download():
    client = FakeClient()
    report = estimate_costs(client, remaining_credit_usd=125)
    assert len(client.metadata.calls) == 6
    assert report["sum_if_all_schemas_requested_usd"] == 25.5
    assert report["all_estimates_within_reported_credit"]
    assert report["has_downloaded_market_data"] is False
    assert report["has_made_purchase"] is False


def test_no_assumptions_about_existing_credits():
    r = estimate_costs(FakeClient())
    assert r["remaining_free_credit_usd_user_supplied"] is None
    assert r["all_estimates_within_reported_credit"] is None


def test_invalid_date_and_credits_fail_closed():
    with pytest.raises(ValueError):
        estimate_costs(FakeClient(), end="2026-09-01T00:00:00Z")
    with pytest.raises(ValueError):
        estimate_costs(FakeClient(), remaining_credit_usd=-1)
