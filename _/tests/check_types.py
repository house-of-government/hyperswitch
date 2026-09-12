#!/usr/bin/env python3
"""Finite-rule audit plus real compiler/runtime and negative-compilation checks.

--source-only never claims to have typechecked or executed Idric.
The full target exits 77 (not success) when the requested compiler is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "_" / "build" / "type-contract"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def choice(source: str, name: str) -> list[str]:
    match = re.search(rf"^choice {name} one_of\n((?:  [a-z0-9_]+\n)+)", source, re.M)
    require(match is not None, f"missing finite choice: {name}")
    return match[1].split()


def declaration(source: str, name: str) -> str:
    match = re.search(rf"^data {name} : [^\n]+ where\n((?:  [^\n]+\n)+)", source, re.M)
    require(match is not None, f"missing indexed family: {name}")
    return match[1]


def clauses(source: str, name: str) -> list[tuple[str, str]]:
    return re.findall(rf"^{name} (.+?) = (.+)$", source, re.M)


def rejection_cases() -> list[dict[str, str]]:
    baseline = json.loads((ROOT / "_/tests/type_baseline.json").read_text())
    specs = []
    for before, after in itertools.product(baseline["payment_method_statuses"], repeat=2):
        if [before, after] not in baseline["transitions"]:
            specs.append({
                "name": "transition_" + before.removeprefix("payment_method_") + "_to_" + after.removeprefix("payment_method_"),
                "type": "PaymentMethodChange (payment_method_inactive, payment_method_active)",
                "valid": "MkPaymentMethodChange (payment_method_inactive, payment_method_active) Inactive_to_active",
                "invalid_type": f"PaymentMethodChange ({before}, {after})",
                "invalid": f"MkPaymentMethodChange ({before}, {after}) Inactive_to_active"})
    specs.extend(json.loads((ROOT / "_/tests/type_rejections.json").read_text()))
    prefix = "module Main\n\nimport HyperSwitch.Connector\nimport HyperSwitch.PaymentMethod\n\n%default total\n\n"
    return [{"name": item["name"],
             "positive": prefix + f"accepted : {item['type']}\naccepted = {item['valid']}\n",
             "negative": prefix + f"rejected : {item.get('invalid_type', item['type'])}\nrejected = {item['invalid']}\n"}
            for item in specs]


def source_audit() -> dict:
    baseline = json.loads((ROOT / "_/tests/type_baseline.json").read_text())
    connector = (ROOT / "HyperSwitch/Connector.idric").read_text()
    payment = (ROOT / "HyperSwitch/PaymentMethod.idric").read_text()
    providers, methods, statuses = (baseline[key] for key in
        ("connectors", "payment_methods", "payment_method_statuses"))
    require(choice(connector, "connector") == providers, "connector domain drift")
    require(choice(payment, "payment_method") == methods, "payment-method domain drift")
    require(choice(payment, "payment_method_status") == statuses, "state domain drift")
    require(choice(payment, "customer_payment_lookup") ==
            ["lookup_saved_customer_method", "skip_customer_method_lookup"], "lookup domain drift")
    require(choice(payment, "locker_id_policy") ==
            ["persist_locker_id", "omit_locker_id"], "locker policy domain drift")
    for name, source in (("Connector", connector), ("PaymentMethod", payment)):
        code = re.sub(r"--[^\n]*", "", source)
        require("%default total" in code, f"{name}: missing totality requirement")
        require(not re.search(r"\b(believe_me|assert_total|assert_smaller|postulate|partial)\b|\?[a-zA-Z_]", code),
                f"{name}: unchecked escape or hole")
        require(not re.search(r"\b(String|Int|Integer|Double|Float|Bits[0-9]+)\b", code),
                f"{name}: primitive domain carrier introduced")

    comparisons = 0
    certificate_count = 0
    for family, (old_query, expected_providers) in baseline["rules"].items():
        pair = family == "access_token_support"
        body = declaration(connector, family)
        certificates: dict[str, set] = {}
        for line in body.strip().splitlines():
            require(":" in line, f"malformed constructor: {line}")
            name, signature = line.strip().split(":", 1)
            name = name.strip()
            signature = signature.strip()
            if pair:
                match = re.fullmatch(
                    r"(?:\{0 method : payment_method\} → )?access_token_support \(([a-z0-9_]+), ([a-z0-9_]+)\)", signature)
                require(match is not None, f"unexpected token constructor: {line}")
                provider, method = match.groups()
                require(provider in providers, f"unknown provider: {provider}")
                require(method == "method" or method in methods, f"unknown method: {method}")
                require((method == "method") == signature.startswith("{0 method"), "method must be an erased index")
                certificates[name] = {(provider, m) for m in (methods if method == "method" else [method])}
            else:
                match = re.fullmatch(rf"{family} ([a-z0-9_]+)", signature)
                require(match is not None and match[1] in providers, f"unexpected certificate: {line}")
                certificates[name] = {match[1]}
        certificate_count += len(certificates)
        expected = {(c, m) for c in expected_providers for m in methods} if pair else set(expected_providers)
        if pair:
            expected |= {("trustpay", m) for m in baseline["trustpay_token_methods"]}
        allowed = set().union(*certificates.values())
        require(allowed == expected, f"{family}: constructor indices differ from baseline")
        seen: set = set()
        lookup = clauses(connector, family + "_for")
        require(lookup and lookup[-1] == ("_", "Nothing"), f"{family}: missing fail-closed fallback")
        require(len(lookup) == len(certificates) + 1, f"{family}: lookup/constructor count mismatch")
        for pattern, result in lookup[:-1]:
            match = re.fullmatch(r"Just ([A-Z][a-zA-Z0-9_]*)", result)
            require(match is not None and match[1] in certificates, f"{family}: unrecognised lookup result")
            if pair:
                match_pattern = re.fullmatch(r"\(([a-z0-9_]+), ([a-z0-9_]+)\)", pattern)
                require(match_pattern is not None, f"{family}: unrecognised pair pattern")
                c, m = match_pattern.groups()
                values = {(c, x) for x in (methods if m == "_" else [m])}
            else:
                values = {pattern}
            require(values == certificates[match[1]], f"{family}: lookup attaches the wrong certificate")
            require(not (seen & values), f"{family}: shadowed rule")
            seen |= values
        require(seen == expected, f"{family}: lookup coverage drift")
        if pair:
            projection = f"{old_query} provider method = capability_present ({family}_for (provider, method))"
        elif family == "order_creation_requirement":
            projection = f"{old_query} provider _ = capability_present ({family}_for provider)"
        else:
            projection = f"{old_query} provider = capability_present ({family}_for provider)"
        left, right = projection.split(" = ", 1)
        require(clauses(connector, old_query) == [(left.removeprefix(old_query + " "), right)],
                f"{old_query}: compatibility query must be a projection, not a second table")
        # Explicitly enumerate the complete input domain, not just positive examples.
        method_independent_pair = family == "order_creation_requirement"
        domain = itertools.product(providers, methods) if pair or method_independent_pair else providers
        for value in domain:
            tested_value = value[0] if method_independent_pair else value
            require((tested_value in allowed) == (tested_value in expected), f"{family}: unexpected decision for {value}")
            comparisons += 1

    edges = baseline["transitions"]
    body = declaration(payment, "payment_method_transition")
    constructors = re.findall(r"^  ([A-Z][a-zA-Z0-9_]*) : payment_method_transition \(([a-z0-9_]+), ([a-z0-9_]+)\)$", body, re.M)
    require(len(constructors) == len(body.strip().splitlines()) == 4, "transition constructor shape drift")
    require({(f, t) for _, f, t in constructors} == {tuple(x) for x in edges}, "transition edge drift")
    lookup = clauses(payment, "payment_method_transition_for")
    require(lookup[-1:] == [("_", "Nothing")], "transition lookup missing fail-closed fallback")
    require(lookup[:-1] == [(f"({f}, {t})", f"Just {name}") for name, f, t in constructors], "transition lookup drift")
    for before, after in itertools.product(statuses, statuses):
        require(((before, after) in {(f, t) for _, f, t in constructors}) == ([before, after] in edges), "transition mismatch")
        comparisons += 1
    require("case payment_method_transition_for (before, after) of\n    Nothing ⇒ False\n    Just _ ⇒ True" in payment,
            "transition Bool must derive from its certificate lookup")

    policy = clauses(payment, "locker_id_policy_for")
    for method in methods:
        for mode in ("lookup_saved_customer_method", "skip_customer_method_lookup"):
            result = None
            for pattern, value in policy:
                match = re.fullmatch(r"\(([a-z0-9_]+), ([a-z0-9_]+)\)", pattern)
                require(pattern == "_" or match is not None, "unrecognised policy pattern")
                if pattern == "_" or (match[1] in ("_", method) and match[2] in ("_", mode)):
                    result = value
                    break
            expected = method in ("card", "bank_debit", "bank_redirect") or (method == "wallet" and mode == "skip_customer_method_lookup")
            require(result == ("persist_locker_id" if expected else "omit_locker_id"), "locker policy drift")
            comparisons += 1

    # Check the two plan signatures retain exactly the caller's indices and
    # that checking-only evidence is erased, not an unrestricted Bool field.
    for source, name, index_type, family, variable, arg in (
        (connector, "AccessTokenPlan", "connector, payment_method", "access_token_support", "selection", "capability"),
        (payment, "PaymentMethodChange", "payment_method_status, payment_method_status", "payment_method_transition", "edge", "permitted")):
        require(f"data {name} : ({index_type}) → Type where" in source, f"{name}: result indices lost")
        require(f"(0 {arg} : {family} {variable}) →" in source, f"{name}: constraint missing or not erased")
        require(f"Maybe ({name} {variable})" in source, f"{name}: dynamic result forgets its selection")
        require(f"Just {arg} ⇒ Just (Mk{name} {variable} {arg})" in source, f"{name}: unsafe planner body")

    rejections = rejection_cases()
    require(len(rejections) == 45, "rejection inventory drift")
    require(len({case['name'] for case in rejections}) == len(rejections), "duplicate rejection names")
    require(sum(case['name'].startswith('transition_') for case in rejections) == 32, "not all illegal transitions covered")
    for case in rejections:
        require(case['positive'].startswith('module Main\n') and case['negative'].startswith('module Main\n'), "missing paired control")
        require('?' not in case['positive'] + case['negative'], "holes cannot be typechecking controls")
    return {"status": "PASS", "kind": "source-rule audit, not compiler execution",
            "source_comparisons": comparisons, "indexed_capability_constructors": certificate_count,
            "transition_constructors": len(constructors), "negative_compile_cases": len(rejections),
            "baseline_commit": baseline['source_commit'], "baseline_blobs": baseline['source_blobs']}


def execute(command: list[str], log: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout)
    return result


def compiler_tests(compiler: str) -> dict:
    executable = shutil.which(compiler)
    if not executable:
        return {"status": "SKIP", "reason": f"compiler executable not found: {compiler}"}
    version = execute([executable, "--version"], OUTPUT / "compiler-version.log")
    require(version.returncode == 0, "compiler --version failed")
    build = execute([executable, "--build", "hyperswitch.ipkg"], OUTPUT / "package-build.log")
    require(build.returncode == 0, "package build failed; no rejection counts as PASS")
    runtime_tests = ["AttemptStatusTests", "PaymentMethodTests", "ConnectorTests", "TypeContractTests"]
    for name in runtime_tests:
        binary = "hyperswitch-" + name.lower()
        compiled = execute([executable, f"tests/{name}.idric", "-o", binary], OUTPUT / (name + "-compile.log"))
        require(compiled.returncode == 0, f"{name}: compilation failed")
        result = execute([str(ROOT / "build" / "exec" / binary)], OUTPUT / (name + "-run.log"))
        require(result.returncode == 0 and "FAIL" not in result.stdout, f"{name}: runtime checks failed")
        if name == "TypeContractTests":
            require(len(re.findall(r"^PASS .* cases$", result.stdout, re.M)) == 9, "type matrix did not run all groups")
        print(f"PASS compiler/runtime: {name}")

    cases = rejection_cases()
    mismatch = re.compile(r"Mismatch between|Can't solve constraint|When unifying|Type mismatch|Can't find an implementation", re.I)
    infrastructure = re.compile(r"Undefined name|Module .* not found|Can't find import|File error|Unsolved holes|Parse error", re.I)
    for case in cases:
        require(re.fullmatch(r"[a-z0-9_]+", case['name']) is not None, "unsafe test-case name")
        case_dir = OUTPUT / "negative" / case['name']
        case_dir.mkdir(parents=True, exist_ok=True)
        for build_name in ("positive-build", "negative-build"):
            shutil.rmtree(case_dir / build_name, ignore_errors=True)
        # The same physical source path and fresh build directory prevent a
        # missing import/syntax difference or cached positive from passing.
        stage = case_dir / "Main.idric"
        stage.write_text(case['positive'])
        control = execute([executable, "--build-dir", str(case_dir / "positive-build"), "--check", str(stage)], case_dir / "positive.log")
        require(control.returncode == 0, f"positive control failed: {case['name']}")
        stage.write_text(case['negative'])
        rejected = execute([executable, "--build-dir", str(case_dir / "negative-build"), "--check", str(stage)], case_dir / "negative.log")
        require(rejected.returncode != 0 and mismatch.search(rejected.stdout) and not infrastructure.search(rejected.stdout),
                f"did not reject for an expected type mismatch: {case['name']}")
        print(f"PASS rejected illegal construction: {case['name']}")
    return {"status": "PASS", "compiler": str(executable), "version": version.stdout.strip(),
            "runtime_executables": len(runtime_tests), "negative_controls_and_rejections": len(cases)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true", help="run the source-rule audit only; never report compiler success")
    parser.add_argument("--compiler", default=os.environ.get("IDRIC", "idris2"), help="current Idric compiler executable, not the bootstrap launcher")
    arguments = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    receipt: dict = {"source": {"status": "NOT_RUN"}, "compiler": {"status": "NOT_RUN"}}
    try:
        receipt['source'] = source_audit()
        print(f"PASS source-rule comparisons: {receipt['source']['source_comparisons']}")
        if arguments.source_only:
            receipt['compiler'] = {"status": "NOT_RUN", "reason": "--source-only requested"}
            print("NOT_RUN compiler/runtime/negative-compilation checks (--source-only)")
            code = 0
        else:
            receipt['compiler'] = compiler_tests(arguments.compiler)
            code = 0 if receipt['compiler']['status'] == 'PASS' else 77
            if code:
                print(f"SKIP compiler/runtime/negative-compilation checks: {receipt['compiler']['reason']}")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        receipt['error'] = str(error)
        failed_stage = 'source' if receipt['source']['status'] == 'NOT_RUN' else 'compiler'
        receipt[failed_stage] = {"status": "FAIL", "reason": str(error)}
        print(f"FAIL {error}", file=sys.stderr)
        code = 1
    receipt['sources_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted((ROOT/'HyperSwitch').glob('*.idric'))}
    (OUTPUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return code


if __name__ == '__main__':
    sys.exit(main())
