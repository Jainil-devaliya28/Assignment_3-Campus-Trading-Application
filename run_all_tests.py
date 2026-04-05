#!/usr/bin/env python3
# =============================================================================
# run_all_tests.py
# Module B – Master Test Runner
#
# Runs all 5 test scripts in sequence and produces a consolidated
# JSON report for submission.
#
# HOW TO RUN:
#   python run_all_tests.py
#
# OUTPUT:
#   Individual JSON files per test + master_report.json
# =============================================================================

import subprocess
import sys
import json
import time
import os
import requests
from datetime import datetime

SCRIPTS = [
    ("Test 1 – Concurrency",          "test_1_concurrency.py"),
    ("Test 2 – Race Conditions",       "test_2_race_conditions.py"),
    ("Test 3 – Failure Simulation",    "test_3_failure_simulation.py"),
    # Note: Test 4 (Locust) is run separately via CLI — see README.
    ("Test 5 – ACID Verification",     "test_5_acid_verification.py"),
]

RESULT_FILES = {
    "concurrency":          "concurrency_results.json",
    "race_conditions":      "race_condition_results.json",
    "failure_simulation":   "failure_simulation_results.json",
    "acid_verification":    "acid_verification_results.json",
}


def wait_for_server(url, timeout=30):
    """Wait until the server is ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"✓ Server ready at {url}")
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    print(f"❌ Server not ready at {url} after {timeout}s")
    return False


def start_server():
    """Start the Flask server in background."""
    print("Starting Flask server...")
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    if not wait_for_server("http://localhost:5000/login"):
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise RuntimeError("Failed to start Flask server")
    return proc


def stop_server(proc):
    """Stop the Flask server."""
    print("Stopping Flask server...")
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    print("✓ Server stopped")


def run_script(name, script):
    print(f"\n{'▶' * 60}")
    print(f"  Running: {name}")
    print(f"  Script:  {script}")
    print(f"{'▶' * 60}")
    t0      = time.time()
    result  = subprocess.run(
        [sys.executable, script],
        capture_output=False,   # let output flow to terminal in real-time
        text=True,
    )
    elapsed = time.time() - t0
    success = result.returncode == 0
    print(f"\n  {'✅' if success else '❌'} {name} finished in {elapsed:.1f}s (exit={result.returncode})")
    return {"script": script, "success": success, "elapsed_sec": round(elapsed, 1)}


def build_report(run_results):
    report = {
        "generated_at":   datetime.now().isoformat(),
        "system":         "Campus Trading Platform",
        "module":         "Module B – Multi-User Behaviour & Stress Testing",
        "scripts_run":    run_results,
        "test_results":   {},
    }

    for key, filename in RESULT_FILES.items():
        if os.path.exists(filename):
            with open(filename) as f:
                report["test_results"][key] = json.load(f)
        else:
            report["test_results"][key] = {"error": "Result file not found — test may have crashed"}

    return report


def print_summary(run_results, report):
    print("\n" + "█" * 60)
    print("  MODULE B — MASTER REPORT SUMMARY")
    print("█" * 60)
    for r in run_results:
        icon = "✅" if r["success"] else "❌"
        print(f"  {icon} {r['script']:<40} {r['elapsed_sec']}s")

    print("\n  ACID Property Results:")
    acid = report["test_results"].get("acid_verification", {})
    for prop in ["ATOMICITY", "CONSISTENCY", "ISOLATION", "DURABILITY"]:
        data = acid.get(prop, {})
        if data:
            icon = "✅" if data.get("passed") else "❌"
            score = data.get("score", "?")
            print(f"    {icon} {prop:<15} {score}")

    all_ok = all(r["success"] for r in run_results)
    print("\n" + "─" * 60)
    print(f"  Overall: {'✅ ALL TESTS PASSED' if all_ok else '⚠️  SOME TESTS HAD FAILURES (see individual JSON files)'}")
    print("  Results: master_report.json")
    print("─" * 60)

    print("""
  ╔════════════════════════════════════════════════════════╗
  ║  For Stress Test (Locust):                             ║
  ║  Run AFTER starting your Flask app:                    ║
  ║                                                        ║
  ║  locust -f test_4_locust_stress.py \\                  ║
  ║         --headless --users 50 --spawn-rate 10 \\       ║
  ║         --run-time 60s \\                              ║
  ║         --host http://localhost:5000 \\                ║
  ║         --csv stress_results \\                        ║
  ║         --html stress_report.html                      ║
  ╚════════════════════════════════════════════════════════╝
""")


def main():
    print("\n" + "█" * 60)
    print("  MODULE B – MASTER TEST RUNNER")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("█" * 60)

    server_proc = None
    try:
        server_proc = start_server()

        run_results = []
        for name, script in SCRIPTS:
            res = run_script(name, script)
            run_results.append(res)
            time.sleep(1)   # brief pause between scripts

        report = build_report(run_results)

        with open("master_report.json", "w") as f:
            json.dump(report, f, indent=2, default=str)

        print_summary(run_results, report)
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        if server_proc:
            stop_server(server_proc)


if __name__ == "__main__":
    sys.exit(main())
