.DEFAULT_GOAL := build

build:
	mkdir -p build
	python3 -m build --outdir build
install: 
	pip install --force-reinstall build/shrinkify-*.*.*.tar.gz
#todo: dynamic version number
clean:
	rm -r build

full: clean build install
	echo "Clean, build, install complete"
