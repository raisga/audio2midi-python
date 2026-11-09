PYTHON ?= python3
VERSION = $(shell PYTHONPATH=src $(PYTHON) -c 'import audio2midi; print(audio2midi.__version__)')
FILE ?= ./sample/djent_rock.mp3

.PHONY: install dev run test smoke lint build release

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

# Creates the GitHub release v$(VERSION) from main, which publishes it to PyPI (see .github/workflows/release.yml).
release:
	@test -z "$$(git status --porcelain)" || { echo "Commit your changes first"; exit 1; }
	git fetch origin main
	@test "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/main)" || { echo "HEAD must match origin/main"; exit 1; }
	gh release create v$(VERSION) --target main --title v$(VERSION) --generate-notes
