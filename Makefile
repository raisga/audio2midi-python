PYTHON ?= python3
FILE ?= ./sample/djent_rock.mp3

.PHONY: install dev run test lint

install:
	$(PYTHON) -m pip install .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

run:
	$(PYTHON) -m audio2midi --verbose --file $(FILE) $(ARGS)

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -t .

lint:
	$(PYTHON) -m ruff check src tests
