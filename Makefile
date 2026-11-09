PYTHON ?= python3
FILE ?= ./sample/djent_rock.mp3

.PHONY: install dev run test smoke lint build

install:
	$(PYTHON) -m pip install .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

run:
	$(PYTHON) -m audio2midi --verbose --file $(FILE) $(ARGS)

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -t .

smoke:
	AUDIO2MIDI_SMOKE=1 $(PYTHON) -m unittest tests.test_smoke -v

lint:
	$(PYTHON) -m ruff check src tests

build:
	rm -rf dist
	$(PYTHON) -m build
	$(PYTHON) -m twine check --strict dist/*
