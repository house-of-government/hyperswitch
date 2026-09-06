# HyperSwitch → Idriç

This branch starts a behavior-preserving Idriç rewrite without deleting the Rust implementation yet. The Rust tree remains the executable reference while pure domain behavior is moved across with acceptance checks.

## Converted seams

### Attempt status

`HyperSwitch/Attempt.idric` ports `AttemptStatus` from `crates/common_enums/src/enums.rs`.

It includes the complete 29-state domain and the existing pure predicates:

- `is_terminal_status`
- `is_payment_terminal_failure`
- `is_success`
- `is_authorization_success`
- `should_update_payment_method`

`tests/AttemptStatusTests.idric` checks the complete true/false truth tables.

### Payment methods

`HyperSwitch/PaymentMethod.idric` ports the 16-case `PaymentMethod` domain and its currently converted pure behavior:

- gift-card classification
- installment support
- locker-ID persistence rules
- the six-state `PaymentMethodStatus` domain
- the complete `AttemptStatus → PaymentMethodStatus` mapping
- allowed payment-method-status transitions

`tests/PaymentMethodTests.idric` checks these rules, including every attempt status in the status conversion.

### Connectors

`HyperSwitch/Connector.idric` ports the connector domain and the first routing/capability predicates from `crates/common_enums/src/connector_enums.rs`:

- access-token support by connector and payment method
- pre-payment order-creation requirement
- file-storage support
- dispute-defense requirement
- separate-authentication support
- overcapture support
- acknowledgement of resource-not-found webhook errors

`tests/ConnectorTests.idric` checks the positive connector sets and representative negatives, including Trustpay's payment-method-specific access-token rule.

## Build

Use the current Idriç compiler executable through `IDRIC`:

```sh
make -f idric.mk
make -f idric.mk test
```

The default remains `idris2`, matching the current Idriç repositories.

## Porting order

Continue with pure domain behavior before infrastructure:

1. remaining routing-relevant `common_enums` domains, especially `PaymentMethodType`, `PayoutType`, and currency decimal semantics
2. deterministic routing decision data and selection logic
3. connector request/response transformations
4. network boundaries through Idric-Net
5. storage and service boundaries last

Do not remove a Rust implementation until its Idriç replacement has mechanical acceptance coverage.
