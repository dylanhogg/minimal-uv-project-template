from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from cookiecutter.main import cookiecutter


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(prefix="cookiecutter-smoke-") as temp_dir:
        cookiecutter(
            str(repo_root),
            no_input=True,
            output_dir=temp_dir,
            overwrite_if_exists=True,
        )

        generated_root = Path(temp_dir) / "my-project"
        required_files = [
            generated_root / "pyproject.toml",
            generated_root / "Makefile",
            generated_root / "src" / "my_project" / "app.py",
            generated_root / "tests" / "my_project" / "test_app.py",
        ]
        missing = [str(path.relative_to(generated_root)) for path in required_files if not path.exists()]
        if missing:
            sys.stderr.write(f"Template render smoke failed. Missing files: {', '.join(missing)}\n")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
