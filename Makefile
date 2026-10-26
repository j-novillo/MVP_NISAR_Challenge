PYTHON ?= .venv/bin/python

.PHONY: install test pipeline nisar visor

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -e .

test:
	$(PYTHON) -m pytest

pipeline:
	$(PYTHON) -m prioridad_galicia.cli pipeline

nisar:
	$(PYTHON) -m prioridad_galicia.cli nisar-buscar

visor:
	$(PYTHON) -m streamlit run app/visor.py
