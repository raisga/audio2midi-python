PYTHON ?= python3
FILE ?= ./sample/djent_rock.mp3

.PHONY: install run test

install:
	$(PYTHON) app/main.py --install

run:
	$(PYTHON) app/main.py --verbose --file $(FILE) $(ARGS)

test:
	$(PYTHON) -m unittest discover -s app/tests -t app
