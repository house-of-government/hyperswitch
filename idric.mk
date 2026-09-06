IDRIC ?= idris2

.PHONY: all test clean

all:
	$(IDRIC) --build hyperswitch.ipkg

test: all
	$(IDRIC) tests/AttemptStatusTests.idric -o hyperswitch-attempt-tests
	./build/exec/hyperswitch-attempt-tests
	$(IDRIC) tests/PaymentMethodTests.idric -o hyperswitch-payment-method-tests
	./build/exec/hyperswitch-payment-method-tests
	$(IDRIC) tests/ConnectorTests.idric -o hyperswitch-connector-tests
	./build/exec/hyperswitch-connector-tests

clean:
	rm -rf build
