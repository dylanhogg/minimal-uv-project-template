from typing import Any

import pytest

from my_project import app


def test_app_main_calls_configure_and_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"configure": 0}

    def fake_configure() -> None:
        calls["configure"] += 1

    def fake_info(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(app.log, "configure", fake_configure)
    monkeypatch.setattr(app.logger, "info", fake_info)

    assert app.main("req_arg_from_tests") == 0
    assert calls["configure"] == 1
