import pytest

from my_project.library import env


def test_env_get_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TEST_ENV", "value")
    assert env.get("MY_TEST_ENV") == "value"


def test_env_get_returns_default_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MY_TEST_ENV", raising=False)
    assert env.get("MY_TEST_ENV", "fallback") == "fallback"


def test_env_get_raises_when_missing_and_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MY_TEST_ENV", raising=False)
    with pytest.raises(ValueError, match=r"MY_TEST_ENV environment variable is not set\."):
        env.get("MY_TEST_ENV")
