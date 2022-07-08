.DEFAULT_GOAL := build

build:
	mkdir -p build
	python3 -m build --outdir build
install: 
	pip install --force-reinstall build/shrinkify-0.0.*.tar.gz
#todo: dynamic version number
clean:
	rm -r build
