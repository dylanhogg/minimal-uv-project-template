from __future__ import annotations

import sys
from pathlib import Path

TEMPLATE_HOOKS_DIR = Path("{{ cookiecutter._template }}") / "hooks"
if TEMPLATE_HOOKS_DIR.exists():
    sys.path.insert(0, str(TEMPLATE_HOOKS_DIR))

from template_contract import required_project_paths

ROOT = Path.cwd()
APP_SLUG = "{{ cookiecutter.app_slug }}"
APP_PACKAGE = "{{ cookiecutter.app_package }}"
LIB_SLUG = "{{ cookiecutter.lib_slug }}"
LIB_PACKAGE = "{{ cookiecutter.lib_package }}"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def verify_required_files() -> None:
    required_files = required_project_paths(
        ROOT,
        app_slug=APP_SLUG,
        app_package=APP_PACKAGE,
        lib_slug=LIB_SLUG,
        lib_package=LIB_PACKAGE,
    )
    missing_files = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    if missing_files:
        fail(f"Generated project is missing required files: {', '.join(missing_files)}")


def normalize_artifacts() -> None:
    for ds_store in ROOT.rglob(".DS_Store"):
        ds_store.unlink(missing_ok=True)


def ensure_no_unrendered_tokens() -> None:
    unresolved_files: list[str] = []
    token_spaced = "{" + "{" + " cookiecutter."
    token_compact = "{" + "{" + "cookiecutter."

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if token_spaced in text or token_compact in text:
            unresolved_files.append(str(path.relative_to(ROOT)))

    if unresolved_files:
        displayed = ", ".join(unresolved_files[:8])
        fail(f"Unrendered cookiecutter tokens found in: {displayed}")


verify_required_files()
normalize_artifacts()
ensure_no_unrendered_tokens()
