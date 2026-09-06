IDRIC ?= idris2
PYTHON ?= python3

.PHONY: all test check-source clean

all:
	$(IDRIC) --build hyperswitch.ipkg

check-source:
	$(PYTHON) _/tests/test_source_audit.py
	$(PYTHON) _/tests/check_types.py --source-only

test:
	$(PYTHON) _/tests/test_source_audit.py
	$(PYTHON) _/tests/check_types.py --compiler "$(IDRIC)"

clean:
	rm -rf build _/build
