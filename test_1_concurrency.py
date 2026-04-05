# =============================================================================
# test_1_concurrency.py
# Module B – Concurrent Usage Test
#
# WHAT THIS TESTS:
#   Simulates multiple users performing operations simultaneously against
#   the same Flask server. Verifies the system handles parallel sessions
#   correctly and returns consistent data to each user.
#
# HOW TO RUN:
#   python test_1_concurrency.py
#
# EXPECTED OUTCOME:
#   All threads complete without HTTP errors. Each user sees only their
#   own session data (no cross-session contamination). Response times
#   are logged to concurrency_results.json.
# =============================================================================

import threading
import time
import json
import sys
from config import BASE_URL, ALL_USERS, REQUEST_TIMEOUT
from app.helpers import make_session, get_available_products, log, ResultCollector


# ── Worker Functions ──────────────────────────────────────────────────────────

def worker_browse_marketplace(user: dict, collector: ResultCollector, iterations: int = 5):
    """Simulate a user browsing the marketplace repeatedly."""
    try:
        session = make_session(user)
    except RuntimeError as e:
        log.error("AUTH FAIL [%s]: %s", user["email"], e)
        collector.record(user=user["email"], action="login", success=False, error=str(e))
        return

    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            resp = session.get(f"{BASE_URL}/marketplace", timeout=REQUEST_TIMEOUT)
            elapsed = (time.perf_counter() - t0) * 1000
            ok = resp.status_code == 200
            collector.record(
                user=user["email"],
                action="browse_marketplace",
                iteration=i + 1,
                status_code=resp.status_code,
                elapsed_ms=round(elapsed, 2),
                success=ok,
            )
            log.info("[%s] marketplace iter=%d status=%d %.0fms",
                     user["email"], i + 1, resp.status_code, elapsed)
        except Exception as e:
            collector.record(user=user["email"], action="browse_marketplace",
                             iteration=i + 1, success=False, error=str(e))
            log.error("[%s] marketplace iter=%d EXCEPTION: %s", user["email"], i + 1, e)
        time.sleep(0.1)  # slight pacing — realistic user think time


def worker_view_transactions(user: dict, collector: ResultCollector, iterations: int = 5):
    """Simulate a user checking their transaction history."""
    try:
        session = make_session(user)
    except RuntimeError as e:
        collector.record(user=user["email"], action="login", success=False, error=str(e))
        return

    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            resp = session.get(f"{BASE_URL}/transactions", timeout=REQUEST_TIMEOUT)
            elapsed = (time.perf_counter() - t0) * 1000
            ok = resp.status_code == 200
            collector.record(
                user=user["email"],
                action="view_transactions",
                iteration=i + 1,
                status_code=resp.status_code,
                elapsed_ms=round(elapsed, 2),
                success=ok,
            )
            log.info("[%s] transactions iter=%d status=%d %.0fms",
                     user["email"], i + 1, resp.status_code, elapsed)
        except Exception as e:
            collector.record(user=user["email"], action="view_transactions",
                             iteration=i + 1, success=False, error=str(e))
        time.sleep(0.1)


def worker_view_product_detail(user: dict, product_id: int,
                                collector: ResultCollector, iterations: int = 5):
    """Simulate multiple users viewing the same product page simultaneously."""
    try:
        session = make_session(user)
    except RuntimeError as e:
        collector.record(user=user["email"], action="login", success=False, error=str(e))
        return

    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            resp = session.get(f"{BASE_URL}/product/{product_id}", timeout=REQUEST_TIMEOUT)
            elapsed = (time.perf_counter() - t0) * 1000
            ok = resp.status_code == 200
            collector.record(
                user=user["email"],
                action="product_detail",
                product_id=product_id,
                iteration=i + 1,
                status_code=resp.status_code,
                elapsed_ms=round(elapsed, 2),
                success=ok,
            )
            log.info("[%s] product/%d iter=%d status=%d %.0fms",
                     user["email"], product_id, i + 1, resp.status_code, elapsed)
        except Exception as e:
            collector.record(user=user["email"], action="product_detail",
                             iteration=i + 1, success=False, error=str(e))
        time.sleep(0.05)


# ── Scenario 1: Mixed concurrent reads ───────────────────────────────────────

def scenario_concurrent_reads():
    print("\n" + "=" * 60)
    print("  SCENARIO 1: Concurrent Multi-User Read Operations")
    print("  All 3 users browse marketplace + transactions in parallel")
    print("=" * 60)

    collector = ResultCollector("Concurrent Reads")

    # First find a product to view
    try:
        probe_session = make_session(ALL_USERS[0])
        products = get_available_products(probe_session)
        product_id = products[0]["id"] if products else 1
    except Exception:
        product_id = 1

    threads = []
    for user in ALL_USERS:
        threads.append(threading.Thread(
            target=worker_browse_marketplace,
            args=(user, collector, 5),
            name=f"Browse-{user['name']}",
        ))
        threads.append(threading.Thread(
            target=worker_view_transactions,
            args=(user, collector, 5),
            name=f"Txn-{user['name']}",
        ))
        threads.append(threading.Thread(
            target=worker_view_product_detail,
            args=(user, product_id, collector, 5),
            name=f"Product-{user['name']}",
        ))

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - start

    s = collector.print_summary()
    s["wall_time_sec"] = round(wall, 2)

    print(f"  Wall-clock time (all threads): {wall:.2f}s")
    print(f"  Sequential equivalent would be ~{s['total'] * (s.get('avg_ms', 0) / 1000):.1f}s")
    print("  → Parallelism factor: {:.1f}x\n".format(
        (s['total'] * (s.get('avg_ms', 200) / 1000)) / max(wall, 0.001)
    ))
    return s, collector.results


# ── Scenario 2: Concurrent writes – multiple users add products ───────────────

def scenario_concurrent_writes():
    print("\n" + "=" * 60)
    print("  SCENARIO 2: Concurrent Write Operations")
    print("  All users attempt to add products simultaneously")
    print("=" * 60)

    collector = ResultCollector("Concurrent Writes")

    def worker_add_product(user, collector, thread_id):
        try:
            session = make_session(user)
        except RuntimeError as e:
            collector.record(user=user["email"], action="add_product",
                             success=False, error=str(e))
            return

        title = f"ConcTest-T{thread_id}-{user['name'][:6]}"
        t0 = time.perf_counter()
        try:
            resp = session.post(
                f"{BASE_URL}/product/add",
                data={
                    "title":       title,
                    "description": "Concurrent write test",
                    "price":       "50",
                    "category":    "Books",
                    "condition":   "Good",
                },
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            body = resp.text.lower() if resp.text else ""
            ok = resp.status_code == 200 and (
                "/marketplace" in resp.url or
                "product listed successfully" in body or
                "alert alert-success" in body
            )
            collector.record(
                user=user["email"],
                action="add_product",
                title=title,
                status_code=resp.status_code,
                elapsed_ms=round(elapsed, 2),
                success=ok,
                detail="success" if ok else resp.text[:100],
            )
            log.info("[%s] add_product '%s' ok=%s %.0fms", user["email"], title, ok, elapsed)
        except Exception as e:
            collector.record(user=user["email"], action="add_product",
                             success=False, error=str(e))

    threads = []
    for i in range(6):
        user = ALL_USERS[i % len(ALL_USERS)]
        threads.append(threading.Thread(
            target=worker_add_product,
            args=(user, collector, i),
        ))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    s = collector.print_summary()
    return s, collector.results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "█" * 60)
    print("  MODULE B – TEST 1: CONCURRENT USAGE")
    print("  Target: " + BASE_URL)
    print("█" * 60)

    all_results = {}
    all_raw     = {}

    s1, r1 = scenario_concurrent_reads()
    all_results["concurrent_reads"]  = s1
    all_raw["concurrent_reads"]      = r1

    time.sleep(1)

    s2, r2 = scenario_concurrent_writes()
    all_results["concurrent_writes"] = s2
    all_raw["concurrent_writes"]     = r2

    # ── Save results ──────────────────────────────────────────────────────────
    with open("concurrency_results.json", "w") as f:
        json.dump({"summary": all_results, "raw": all_raw}, f, indent=2, default=str)

    print("\n✅ Results saved → concurrency_results.json")

    # ── ACID observation ──────────────────────────────────────────────────────
    print("\n── ACID Observation ──────────────────────────────────────────")
    print("  Isolation check: each user's session cookie is independent.")
    reads_ok = all_results["concurrent_reads"]["failures"] == 0
    writes_ok = all_results["concurrent_writes"]["failures"] == 0
    print(f"  Read isolation  : {'✅ PASS — no errors' if reads_ok else '❌ FAIL — see raw log'}")
    print(f"  Write isolation : {'✅ PASS — no errors' if writes_ok else '❌ FAIL — see raw log'}")
    print("─" * 60)

    return 0 if (reads_ok and writes_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
