import os


def get(name: str, default: str | None = None) -> str | None:
    if os.getenv(name) is None and default is None:
        raise ValueError(f"{name} environment variable is not set.")
    elif os.getenv(name) is None:
        return default
    else:
        return os.environ[name]
