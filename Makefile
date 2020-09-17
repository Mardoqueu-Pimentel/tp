AUTOFLAKE_OPTS ?= --ignore-init-module-imports --remove-all-unused-imports --remove-unused-variables
BLACK_OPTS ?= --line-length 100 --target-version py311
ISORT_OPTS ?= --multi-line 3 --trailing-comma --line-width 100
FLAKE8_OPTS ?= --max-line-length 100 --ignore E203,W503
MYPY_OPTS ?= --ignore-missing-imports

PYTHON_FILES ?= $(shell find src -type f -name '*.py')

autoflake:
	@!(autoflake $(AUTOFLAKE_OPTS) $(PYTHON_FILES) | grep -v 'No issues detected!$$')

autoflake-formatter: AUTOFLAKE_OPTS := $(AUTOFLAKE_OPTS) --in-place
autoflake-formatter: autoflake

autoflake-linter: AUTOFLAKE_OPTS := $(AUTOFLAKE_OPTS) --check
autoflake-linter: autoflake

isort:
	@isort $(ISORT_OPTS) $(PYTHON_FILES)

black:
	@black $(BLACK_OPTS) $(PYTHON_FILES)

black-formatter: black

black-linter: BLACK_OPTS := $(BLACK_OPTS) --check
black-linter: black

format: autoflake-formatter isort black

mypy:
	@mypy $(MYPY_OPTS) $(PYTHON_FILES)

flake8:
	@flake8 $(FLAKE8_OPTS) $(PYTHON_FILES)

lint: ISORT_OPTS := $(ISORT_OPTS) --check-only
lint: autoflake-linter isort black-linter mypy

test: export PYTHONHASHSEED=0
test:
	pytest -vv -rA --capture=fd $(ARGS)

release-patch:
	poetry version patch && poetry install

release-minor:
	poetry version minor && poetry install

release-major:
	poetry version major && poetry install
