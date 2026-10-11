"""
tests/e2e/runner.py
Tiered E2E Test Runner CLI for AgriAgent.

Usage:
    python3 tests/e2e/runner.py --all             # Run all E2E tiers (Tiers 1 to 4)
    python3 tests/e2e/runner.py --tier 1          # Run Tier 1 (Feature Coverage) only
    python3 tests/e2e/runner.py --tier 2          # Run Tier 2 (Boundary & Robustness) only
    python3 tests/e2e/runner.py --tier 3          # Run Tier 3 (Cross-Feature Pairwise) only
    python3 tests/e2e/runner.py --tier 4          # Run Tier 4 (Real-World Field Scenarios) only
    python3 tests/e2e/runner.py --all --json      # Output machine-readable JSON summary for CI/CD
    python3 tests/e2e/runner.py --all -v          # Verbose test-level execution logging
"""

import argparse
import json
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class JSONTestResult(unittest.TestResult):
    """Custom TestResult that captures structured execution records for CI/CD."""

    def __init__(self):
        super().__init__()
        self.records: List[Dict[str, Any]] = []

    def startTest(self, test: unittest.TestCase):
        super().startTest(test)
        self._start_time = time.time()

    def addSuccess(self, test: unittest.TestCase):
        super().addSuccess(test)
        elapsed = time.time() - getattr(self, "_start_time", time.time())
        self.records.append({
            "test_id": test.id(),
            "status": "PASS",
            "duration_seconds": round(elapsed, 4),
            "message": None,
        })

    def addFailure(self, test: unittest.TestCase, err):
        super().addFailure(test, err)
        elapsed = time.time() - getattr(self, "_start_time", time.time())
        self.records.append({
            "test_id": test.id(),
            "status": "FAIL",
            "duration_seconds": round(elapsed, 4),
            "message": self._exc_info_to_string(err, test),
        })

    def addError(self, test: unittest.TestCase, err):
        super().addError(test, err)
        elapsed = time.time() - getattr(self, "_start_time", time.time())
        self.records.append({
            "test_id": test.id(),
            "status": "ERROR",
            "duration_seconds": round(elapsed, 4),
            "message": self._exc_info_to_string(err, test),
        })

    def addSkip(self, test: unittest.TestCase, reason: str):
        super().addSkip(test, reason)
        elapsed = time.time() - getattr(self, "_start_time", time.time())
        self.records.append({
            "test_id": test.id(),
            "status": "SKIP",
            "duration_seconds": round(elapsed, 4),
            "message": reason,
        })


def build_suite_for_tier(tier: Optional[int] = None) -> unittest.TestSuite:
    """Load test suites based on selected tier."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    here = Path(__file__).resolve().parent

    tier_patterns = {
        1: "test_tier1_*.py",
        2: "test_tier2_*.py",
        3: "test_tier3_*.py",
        4: "test_tier4_*.py",
    }

    if tier is not None:
        pattern = tier_patterns.get(tier)
        if pattern:
            suite.addTests(loader.discover(start_dir=str(here), pattern=pattern))
    else:
        for pattern in tier_patterns.values():
            suite.addTests(loader.discover(start_dir=str(here), pattern=pattern))

    return suite


def run_e2e(tier: Optional[int] = None, verbose: bool = False, output_json: bool = False) -> int:
    """Execute E2E test suite and report results."""
    suite = build_suite_for_tier(tier)
    tier_label = f"Tier {tier}" if tier is not None else "All Tiers (Tiers 1 to 4)"

    if not output_json:
        print("=" * 70)
        print(f" AgriAgent E2E Testing Track Runner — {tier_label}")
        print("=" * 70)

    start_time = time.time()

    if output_json:
        result = JSONTestResult()
        suite.run(result)
        elapsed = time.time() - start_time

        summary = {
            "tier": tier_label,
            "total": result.testsRun,
            "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
            "failed": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "elapsed_seconds": round(elapsed, 4),
            "records": result.records,
        }
        print(json.dumps(summary, indent=2))
        return 0 if (len(result.failures) == 0 and len(result.errors) == 0) else 1
    else:
        verbosity = 2 if verbose else 1
        runner = unittest.TextTestRunner(verbosity=verbosity)
        res = runner.run(suite)
        elapsed = time.time() - start_time

        print("\n" + "=" * 70)
        print(f" Summary: {res.testsRun} tests run in {elapsed:.3f}s")
        print(f" Passed:  {res.testsRun - len(res.failures) - len(res.errors) - len(res.skipped)}")
        print(f" Failed:  {len(res.failures)}")
        print(f" Errors:  {len(res.errors)}")
        print(f" Skipped: {len(res.skipped)}")
        print("=" * 70)

        return 0 if res.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description="AgriAgent E2E Test Track Runner")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run a specific test tier (1, 2, 3, or 4)")
    group.add_argument("--all", action="store_true", default=True, help="Run all E2E test tiers")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test execution logging")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON summary")

    args = parser.parse_args()
    tier = args.tier if args.tier is not None else (None if args.all else None)
    exit_code = run_e2e(tier=tier, verbose=args.verbose, output_json=args.json)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
