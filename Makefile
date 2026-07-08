.PHONY: help install run test clean build package

help:
	@echo "Perler Beads Designer - Make Commands"
	@echo "===================================="
	@echo "make install     : Install dependencies"
	@echo "make run         : Run the application"
	@echo "make test        : Run tests"
	@echo "make clean       : Clean cache and build files"
	@echo "make build       : Build executable"
	@echo "make package     : Create distribution package"

install:
	pip install -r requirements.txt

run:
	python -m src.main

test:
	python -m pytest tests/ -v

clean:
	rm -rf build dist *.egg-info __pycache__ src/__pycache__ tests/__pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build:
	pip install pyinstaller
	pyinstaller pyinstaller.spec

package:
	python setup.py sdist bdist_wheel

lint:
	pip install pylint
	pylint src/

format:
	pip install black
	black src/ tests/

venv:
	python3 -m venv venv
	@echo "Virtual environment created. Activate it with: source venv/bin/activate"

dev-install: venv install
	pip install pytest pylint black

all: clean install test
