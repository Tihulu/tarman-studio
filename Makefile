.PHONY: install uninstall test dist appimage clean

VERSION := $(shell python3 -c 'import re, pathlib; print(re.search(r"__version__ = \"([^\"]+)\"", pathlib.Path("tarman/__init__.py").read_text()).group(1))')

install:
	./install-pyenv.sh

uninstall:
	./uninstall-pyenv.sh

test:
	python3 -m pytest -q

dist:
	mkdir -p dist
	git archive --format=tar.gz --prefix=tarman-studio-$(VERSION)/ -o dist/tarman-studio-$(VERSION).tar.gz HEAD
	git archive --format=zip --prefix=tarman-studio-$(VERSION)/ -o dist/tarman-studio-$(VERSION).zip HEAD

appimage:
	./scripts/build-appimage.sh

clean:
	rm -rf build dist .pytest_cache */__pycache__ __pycache__
