#!/usr/bin/env python3
"""Adapt the rule audit to current Idric's capitalised data identifiers.

The public snake_case indexed-family names remain exported aliases.  The audit
still checks the same constructor indices and additionally requires each alias
to be definitionally equal to the compiler-legal data family.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("type_contract_audit_core", HERE / "check_types.py")
core = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(core)

ROOT = core.ROOT
OUTPUT = core.OUTPUT

INDEX_TYPES = {
    "access_token_support": "(connector, payment_method)",
    "order_creation_requirement": "connector",
    "file_storage_support": "connector",
    "dispute_defence_requirement": "connector",
    "separate_authentication_support": "connector",
    "overcapture_support": "connector",
    "missing_webhook_acknowledgement": "connector",
    "payment_method_transition": "(payment_method_status, payment_method_status)",
}


def canonical_type(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def declaration(source: str, name: str) -> str:
    actual = canonical_type(name) if name in INDEX_TYPES else name
    match = re.search(rf"^data {actual} : [^\n]+ where\n((?:  [^\n]+\n)+)", source, re.M)
    core.require(match is not None, f"missing indexed family: {name} ({actual})")
    if name in INDEX_TYPES:
        alias = f"{name} : {INDEX_TYPES[name]} → Type\n{name} = {actual}"
        core.require(alias in source, f"missing public snake_case alias: {name}")
    return match[1].replace(actual, name)


core.declaration = declaration


def _sync_paths() -> None:
    core.ROOT = ROOT
    core.OUTPUT = OUTPUT


def source_audit() -> dict:
    _sync_paths()
    return core.source_audit()


def rejection_cases() -> list[dict[str, str]]:
    _sync_paths()
    return core.rejection_cases()


def main() -> int:
    _sync_paths()
    return core.main()


if __name__ == "__main__":
    sys.exit(main())
