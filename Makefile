.PHONY: test bench clean figures
PY ?= python3

test:
	$(PY) tools/oracle.py -v

figures:
	$(PY) docs/make_figures.py

clean:
	rm -rf build __pycache__ pythia/__pycache__ docs/_arch.dot

# --- PYTHIA Studio packaging ---
.PHONY: studio wheel docker check-package

studio:            ## run the app from this checkout (creates .venv on first run)
	./studio.sh

wheel:             ## build dist/pythia_studio-*.whl
	$(PY) -m pip wheel --no-deps -w dist .

docker:            ## build the container image
	docker build -t pythia-studio .

check-package:     ## wheel -> fresh venv -> boot -> offline demo job
	scripts/check_package.sh
