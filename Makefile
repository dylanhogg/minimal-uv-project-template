.PHONY: template-test template-precommit template-docker-smoke help

COOKIECUTTER_VERSION ?= 2.6.0
PYTEST_VERSION ?= 9.0.2
TMP_PROJECT_DIR ?= /tmp/my-project

template-test:
	uv run --with pytest==$(PYTEST_VERSION) --with cookiecutter==$(COOKIECUTTER_VERSION) --with 'chardet<6' pytest -q tests/template

template-precommit:
	uv run pre-commit run --all-files

template-docker-smoke:
	rm -rf $(TMP_PROJECT_DIR)
	uvx cookiecutter==$(COOKIECUTTER_VERSION) --no-input . -o /tmp
	cp $(TMP_PROJECT_DIR)/.env_template $(TMP_PROJECT_DIR)/.env
	cd $(TMP_PROJECT_DIR) && uv sync --all-groups
	cd $(TMP_PROJECT_DIR) && uv sync --frozen --all-groups
	cd $(TMP_PROJECT_DIR) && docker compose run --rm app reqarg1 --optional-arg optarg1

template-all: template-test template-precommit template-docker-smoke

.DEFAULT_GOAL := help
help:
	@LC_ALL=C $(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'
