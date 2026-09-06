# HyperSwitch → Idriç

This branch starts a behavior-preserving Idriç rewrite without deleting the Rust implementation yet.

## First converted seam

`HyperSwitch/Attempt.idric` ports `AttemptStatus` from:

`crates/common_enums/src/enums.rs`

The first slice includes the complete 29-state status domain and the existing pure predicates:

- `is_terminal_status`
- `is_payment_terminal_failure`
- `is_success`
- `is_authorization_success`
- `should_update_payment_method`

`tests/AttemptStatusTests.idric` checks the complete true/false truth table for every predicate, so later rewrites can be compared mechanically against the Rust behavior.

## Build

Use the current Idriç compiler executable through `IDRIC`:

```sh
make -f idric.mk
make -f idric.mk test
```

The default remains `idris2`, matching the current Idriç repositories.

## Porting order

Continue with pure domain behavior before infrastructure:

1. connector capability predicates from `crates/common_enums/src/connector_enums.rs`
2. payment-method and currency domains used by routing
3. routing decision data and deterministic selection logic
4. connector request/response transformations
5. network, storage, and service boundaries last

The Rust tree remains the executable reference until equivalent Idriç slices have acceptance coverage.
