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
package_name = "{{ cookiecutter.package_name }}"
author_email = "{{ cookiecutter.author_email }}".strip()

if not SLUG_PATTERN.fullmatch(project_slug):
    fail(
        "project_slug must match ^[a-z][a-z0-9_-]*$ "
        f"(got {project_slug!r})."
    )

if not PACKAGE_PATTERN.fullmatch(package_name):
    fail(
        "package_name must match ^[a-z][a-z0-9_]*$ "
        f"(got {package_name!r})."
    )

if not EMAIL_PATTERN.fullmatch(author_email):
    fail(
        "author_email must be a valid email address "
        f"(got {author_email!r})."
    )
