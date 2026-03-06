from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from cookiecutter.main import cookiecutter
from template_contract import required_project_paths

SMOKE_PROJECT_SLUG = "precommit-smoke-template"
SMOKE_APP_SLUG = SMOKE_PROJECT_SLUG
SMOKE_APP_PACKAGE = "precommit_smoke_template"
SMOKE_LIB_SLUG = "precommit-smoke-template-core"
SMOKE_LIB_PACKAGE = "precommit_smoke_template_core"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(prefix="cookiecutter-smoke-") as temp_dir:
        cookiecutter(
            str(repo_root),
            no_input=True,
            output_dir=temp_dir,
            overwrite_if_exists=True,
            extra_context={
                "project_slug": SMOKE_PROJECT_SLUG,
                "app_slug": SMOKE_APP_SLUG,
                "app_package": SMOKE_APP_PACKAGE,
                "lib_slug": SMOKE_LIB_SLUG,
                "lib_package": SMOKE_LIB_PACKAGE,
            },
        )

        generated_root = Path(temp_dir) / SMOKE_PROJECT_SLUG
        required_files = required_project_paths(
            generated_root,
            app_slug=SMOKE_APP_SLUG,
            app_package=SMOKE_APP_PACKAGE,
            lib_slug=SMOKE_LIB_SLUG,
            lib_package=SMOKE_LIB_PACKAGE,
        )
        missing = [str(path.relative_to(generated_root)) for path in required_files if not path.exists()]
        if missing:
            sys.stderr.write(f"Template render smoke failed. Missing files: {', '.join(missing)}\n")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
