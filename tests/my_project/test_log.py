from typing import Any

import pytest

from my_project.library import log


def test_log_configure_uses_defaults_and_removes_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    removed_calls = {"count": 0}
    add_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_remove(*_args: Any, **_kwargs: Any) -> None:
        removed_calls["count"] += 1

    def fake_add(*args: Any, **kwargs: Any) -> int:
        add_calls.append((args, kwargs))
        return len(add_calls)

    monkeypatch.delenv("LOG_STDERR_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FILE_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FILE_ROTATION", raising=False)
    monkeypatch.setattr(log.logger, "remove", fake_remove)
    monkeypatch.setattr(log.logger, "add", fake_add)

    log.configure()

    assert removed_calls["count"] == 1
    assert len(add_calls) == 2

    stderr_args, stderr_kwargs = add_calls[0]
    assert stderr_args == (log.sys.stderr,)
    assert stderr_kwargs == {"level": "INFO"}

    file_args, file_kwargs = add_calls[1]
    assert file_args == ("./log/app.log",)
    assert file_kwargs["level"] == "DEBUG"
    assert file_kwargs["rotation"] == "00:00"
