IDRIC ?= idris2

.PHONY: all test clean

all:
	$(IDRIC) --build hyperswitch.ipkg

test: all
	$(IDRIC) tests/AttemptStatusTests.idric -o hyperswitch-attempt-tests
	./build/exec/hyperswitch-attempt-tests

clean:
	rm -rf build
