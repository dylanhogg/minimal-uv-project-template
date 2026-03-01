from __future__ import annotations

import re
import sys

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
PACKAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


project_slug = "{{ cookiecutter.project_slug }}"
app_slug = "{{ cookiecutter.app_slug }}"
lib_slug = "{{ cookiecutter.lib_slug }}"
app_package = "{{ cookiecutter.app_package }}"
lib_package = "{{ cookiecutter.lib_package }}"
author_email = "{{ cookiecutter.author_email }}".strip()

for value_name, value in (
    ("project_slug", project_slug),
    ("app_slug", app_slug),
    ("lib_slug", lib_slug),
):
    if not SLUG_PATTERN.fullmatch(value):
        fail(f"{value_name} must match ^[a-z][a-z0-9_-]*$ (got {value!r}).")

for value_name, value in (
    ("app_package", app_package),
    ("lib_package", lib_package),
):
    if not PACKAGE_PATTERN.fullmatch(value):
        fail(f"{value_name} must match ^[a-z][a-z0-9_]*$ (got {value!r}).")

if app_slug == lib_slug:
    fail(f"app_slug and lib_slug must be different (both were {app_slug!r}).")

if app_package == lib_package:
    fail(f"app_package and lib_package must be different (both were {app_package!r}).")

if not EMAIL_PATTERN.fullmatch(author_email):
    fail(
        "author_email must be a valid email address "
        f"(got {author_email!r})."
    )
