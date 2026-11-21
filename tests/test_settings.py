"""Settings: defaults, validation, and the politeness cap."""

import pytest

from sakuna.cli import main
from sakuna.settings import ENV_VARS, MAX_PARALLEL_CAP, load_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    s = load_settings()
    assert s.max_parallel_requests == 6
    assert s.request_timeout_seconds == 60
    assert s.request_retries == 3
    assert s.dromic_base_url == "https://dromic.dswd.gov.ph"
    assert "@" not in s.http_user_agent  # no personal email in the User-Agent


def test_parallel_cap_enforced(monkeypatch):
    monkeypatch.setenv("MAX_PARALLEL_REQUESTS", str(MAX_PARALLEL_CAP + 1))
    with pytest.raises(ValueError, match="MAX_PARALLEL_REQUESTS"):
        load_settings()


@pytest.mark.parametrize("raw", ["0", "abc", "-1"])
def test_bad_parallel_rejected(monkeypatch, raw):
    monkeypatch.setenv("MAX_PARALLEL_REQUESTS", raw)
    with pytest.raises(ValueError, match="MAX_PARALLEL_REQUESTS"):
        load_settings()


def test_empty_value_means_default(monkeypatch):
    monkeypatch.setenv("REQUEST_RETRIES", "  ")
    assert load_settings().request_retries == 3


def test_show_config_runs():
    assert main(["show-config"]) == 0
