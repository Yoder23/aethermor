#!/usr/bin/env python3
"""
Release readiness check.

Verifies that all release gates are met before shipping.
Exit code 0 = ready to release. Non-zero = not ready.
"""
import sys
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_version_consistency():
    """Verify version string is consistent across all locations."""
    print("Checking version consistency...")

    # 1. pyproject.toml
    with open(os.path.join(ROOT, "pyproject.toml"), "r") as f:
        content = f.read()
    m = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not m:
        print("  FAIL: Cannot find version in pyproject.toml")
        return False, None
    version = m.group(1)
    print(f"  pyproject.toml: {version}")

    # 2. README install command
    with open(os.path.join(ROOT, "README.md"), "r") as f:
        readme = f.read()
    wheel_pattern = f"aethermor-{version}-py3-none-any.whl"
    if wheel_pattern not in readme:
        print(f"  FAIL: README install link does not reference {wheel_pattern}")
        return False, version
    print(f"  README wheel: ok")

    # 3. Release notes exist
    rn_path = os.path.join(ROOT, f"RELEASE_NOTES_v{version}.md")
    if not os.path.exists(rn_path):
        print(f"  FAIL: {rn_path} does not exist")
        return False, version
    print(f"  Release notes: ok")

    # 4. No stale release notes presented as current
    for fn in os.listdir(ROOT):
        if fn.startswith("RELEASE_NOTES_v") and fn.endswith(".md"):
            v = fn.replace("RELEASE_NOTES_v", "").replace(".md", "")
            if v != version:
                print(f"  FAIL: Stale release notes found: {fn}")
                return False, version

    # 5. Classifier
    if "4 - Beta" not in content:
        print("  FAIL: pyproject.toml classifier is not Beta")
        return False, version

    print(f"  All version checks pass for v{version}")
    return True, version


def check_docs_exist():
    """Verify all required documentation files exist."""
    print("\nChecking documentation...")
    required = [
        "docs/ACCURACY.md",
        "docs/SAFE_USE.md",
        "docs/INSTALL_VERIFY.md",
        "docs/REPRODUCIBILITY.md",
        "docs/SUPPORT_POLICY.md",
        "docs/SEMVER.md",
        "docs/EXTERNAL_VALIDATION.md",
        "docs/benchmark_protocol.md",
        "docs/CASE_STUDY.md",
        "docs/CASE_STUDY_SOC.md",
        "docs/CASE_STUDY_PARADIGM.md",
        "LIMITATIONS.md",
        "VALIDATION.md",
        "HONEST_REVIEW.md",
        "CHANGELOG.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
    ]
    all_ok = True
    for doc in required:
        path = os.path.join(ROOT, doc)
        exists = os.path.exists(path)
        status = "ok" if exists else "MISSING"
        if not exists:
            all_ok = False
        print(f"  [{status}]  {doc}")
    return all_ok


def check_benchmark_suite():
    """Verify production benchmark suite exists and has cases."""
    print("\nChecking production benchmark suite...")
    cases_csv = os.path.join(ROOT, "benchmarks", "production_suite", "cases.csv")
    if not os.path.exists(cases_csv):
        print("  FAIL: cases.csv not found")
        return False
    with open(cases_csv, "r") as f:
        lines = f.readlines()
    n_cases = len(lines) - 1  # minus header
    if n_cases < 10:
        print(f"  FAIL: Only {n_cases} cases (minimum 10)")
        return False
    print(f"  {n_cases} benchmark cases: ok")

    gold = os.path.join(ROOT, "benchmarks", "gold_outputs", "production_suite_v1.0.0.json")
    if not os.path.exists(gold):
        print("  FAIL: Gold outputs not found")
        return False
    print("  Gold outputs: ok")
    return True


def check_issue_templates():
    """Verify issue templates exist."""
    print("\nChecking issue templates...")
    template_dir = os.path.join(ROOT, ".github", "ISSUE_TEMPLATE")
    if not os.path.exists(template_dir):
        print("  FAIL: .github/ISSUE_TEMPLATE/ not found")
        return False
    templates = os.listdir(template_dir)
    required = ["bug_report.md", "validation_discrepancy.md", "model_question.md"]
    all_ok = True
    for t in required:
        exists = t in templates
        status = "ok" if exists else "MISSING"
        if not exists:
            all_ok = False
        print(f"  [{status}]  {t}")
    return all_ok


def check_scope_statement():
    """Verify scope statement appears in key documents."""
    print("\nChecking scope statement consistency...")
    scope_phrase = "architecture-stage thermal"
    files_to_check = [
        "README.md",
        "LIMITATIONS.md",
        "VALIDATION.md",
        "docs/SAFE_USE.md",
    ]
    all_ok = True
    for fn in files_to_check:
        path = os.path.join(ROOT, fn)
        if not os.path.exists(path):
            print(f"  FAIL: {fn} not found")
            all_ok = False
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if scope_phrase in content:
            print(f"  [ok]  {fn}")
        else:
            print(f"  [MISSING]  {fn} — scope statement not found")
            all_ok = False
    return all_ok


def main():
    print("=" * 60)
    print("AETHERMOR RELEASE READINESS CHECK")
    print("=" * 60)

    results = {}
    ok, version = check_version_consistency()
    results["version"] = ok
    results["docs"] = check_docs_exist()
    results["benchmarks"] = check_benchmark_suite()
    results["templates"] = check_issue_templates()
    results["scope"] = check_scope_statement()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = all(results.values())
    for gate, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}]  {gate}")

    print(f"\n  {'READY TO RELEASE' if all_pass else 'NOT READY'}")
    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
