# HyperSwitch → Idriç

The Rust implementation is unchanged. The Idriç branch is a domain-library
conversion, not a replacement payment service. The current compiler-backed
acceptance suite has passed; this does not broaden the branch into operational
payment behavior.

## Current domain coverage

`HyperSwitch.idric` is the public entrypoint. `HyperSwitch/Attempt.idric`
retains all 29 attempt statuses and the five existing classification queries.
`HyperSwitch/PaymentMethod.idric` retains all 16 payment-method identities,
all six payment-method statuses, and the complete attempt-to-method-status
mapping. `HyperSwitch/Connector.idric` retains all 155 connector identities,
including the existing dummy identities; enumeration is not production
registration or merchant-account configuration.

## Constraints, not just labels

Seven indexed families now represent the existing connector rules:

| Family | Indices |
| --- | --- |
| `access_token_support` | connector and payment method |
| `order_creation_requirement` | connector |
| `file_storage_support` | connector |
| `dispute_defence_requirement` | connector |
| `separate_authentication_support` | connector |
| `overcapture_support` | connector |
| `missing_webhook_acknowledgement` | connector |

Their 39 constructors cover exactly the positive cases in the previous port.
There is no constructor accepting an arbitrary Boolean. For example,
`Trustpay_transfer_token` has type
`access_token_support (trustpay, bank_transfer)`, not the corresponding type
for `card` or `stripe`.

`access_token_support_for` handles a runtime selection and returns either
`Nothing` or a certificate indexed by that exact selection. `plan_access_token`
returns `Maybe (AccessTokenPlan selection)`: it cannot silently substitute a
different selection. The plan constructor requires its certificate with
quantity `0`, so that argument is checking-only rather than a stored flag.

The old `supports_*`/`requires_*` Boolean entrypoints remain compatibility and
display projections of the certificate lookups. They no longer maintain
separate rule tables. Ordinary classification questions, such as whether an
attempt succeeded, are still allowed to return `Bool`.

## State changes

`payment_method_transition (before, after)` has just four constructors:

- inactive → active
- inactive → new
- new → active
- new → inactive

These preserve the existing Rust rule, including its refusal of self-transitions.
`PaymentMethodChange edge` requires a certificate for exactly `edge`, with
checking-only quantity `0`. Its runtime planner returns
`Maybe (PaymentMethodChange edge)`, not an unchecked pair or a Boolean approval.
The old `can_transition_payment_method_status` query derives from this lookup.

A `PaymentMethodChange` is a validated change description. It does not mutate a
stored payment method. A future storage operation must also bind the method ID
and observed version and enforce the transition atomically; types alone do not
prevent concurrent updates or stale database observations.

## Named policies

New code uses `locker_id_policy_for (method, lookup_policy)`. The lookup policy
is either `lookup_saved_customer_method` or `skip_customer_method_lookup`; the
result is `persist_locker_id` or `omit_locker_id`. The former Boolean API is a
compatibility adapter, not the core policy representation.

## Acceptance

```sh
make -f idric.mk check-source
make -f idric.mk test IDRIC=/path/to/current/Idric/_/build/exec/idris2
# Or use the top-level entrypoint with the compiler already on PATH:
./check-types
```

`IDRIC` denotes the built Idriç compiler, currently named `idris2`, not stock
Idris 2 and not the `_/edric` bootstrap launcher. Build from the current Idriç
branch and record its commit; the historical baseline below is a behavior
fixture, not a compiler pin.

The additional runtime matrix covers 5,803 cases: two connector/method products
of 155 × 16, five connector-only domains of 155, all 6 × 6 state transitions,
and both lookup policies for each of 16 payment methods. It also typechecks a
positive value for each capability constructor. The three original test
executables remain in the full suite.

There are 45 negative-compilation cases: all 32 prohibited state edges, plus
wrong-connector, wrong-method, wrong-capability, forged-Boolean, unchecked
optional-certificate, result-index, and primitive-policy/connector cases.
Every rejection has a successful-compilation control. Missing imports, missing
compilers, syntax failures and unresolved holes must not count as rejections.
Separate fresh compilation directories prevent a cached positive from passing
as a negative result.

The Python source audit is intentionally narrow and fail-closed. It compares
finite constructor indices, lookup clauses and compatibility projections with
the frozen pre-refactor rules. Its two unit tests include ten deliberately
broken mutations. It is **not** an Idriç parser, typechecker, runtime or Rust
execution. The full target exits 77, not success, when the compiler is missing.
Logs and a machine-readable receipt are written under `_/build/type-contract/`.

The behavior baseline is `1b64304318bbd50c7d9c91da75a9fc2ffcedd974`.
Both reconstructed pre-refactor source files were checked against their Git
blob hashes before deriving the fixture. The checked-in receipt now records a
real compiler-backed acceptance run against Idriç commit
`d2463ec8a3a0dd4ac167029927452f3e83805dc3`
(`Idris 2, version 0.8.0-d2463ec8a`): all four runtime executables passed, the
runtime matrix covered all 5,803 cases, all 45 positive controls compiled, and
all 45 corresponding illegal constructions were rejected for expected type
mismatches without import/parser/hole infrastructure failures. The receipt is
tied to the exact source hashes and compiler commit and must be regenerated if
either changes.

## Boundaries still to port

Access-token support does not mean permission to move money, nor does its
absence mean a connector cannot accept payments. An order-creation requirement
is not evidence that an order has already been created. Overcapture support
is not evidence that a particular amount is permitted. Credentials, merchant
configuration, amounts, quotas, external responses and storage are not covered
by these certificates.

Money/currency relationships, bounded identifiers, `PaymentMethodType`
compatibility, payout domains, payload validation and routing remain separate
conversion work. They need their actual protocol/provider constraints, not
invented restrictions or renamed `String`/integer carriers. Preserve the Rust
implementation and source-specific behavior while establishing those types.
