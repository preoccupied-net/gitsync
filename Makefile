.PHONY: build build-container test flake8 clean tidy requirements


build:
	tox -qe build


build-container: requirements.txt
	@if command -v podman >/dev/null 2>&1; then \
		podman build -f Containerfile -t preoccupied-gitsync .; \
	elif command -v docker >/dev/null 2>&1; then \
		docker build -f Containerfile -t preoccupied-gitsync .; \
	else \
		echo "Error: neither podman nor docker found"; \
		exit 1; \
	fi


requirements.txt: setup.cfg
	@pip-compile setup.cfg --output-file requirements.txt

requirements: requirements.txt

upgrade:
	@pip-compile --upgrade setup.cfg --output-file requirements.txt


test:
	tox -qe py

flake8:
	tox -qe flake8


clean:
	rm -rf build/* dist/*

tidy:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true


# The end.
