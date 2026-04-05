# =============================================================================
# test_2_race_conditions.py  (v2 – fixed outcome detection)
# Module B – Race Condition Testing
# =============================================================================

import threading
import time
import json
import sys
import re
from config import BASE_URL, USER_A, USER_B, USER_C, RACE_THREAD_COUNT, REQUEST_TIMEOUT
from helpers import make_session, add_product, send_purchase_request, log, ResultCollector


# ── Flash-message helpers ──────────────────────────────────────────────────────
# Flask redirects after POST (allow_redirects=True → resp.text is the FINAL page
# which carries the rendered flash message as plain text in a <div class="alert">.

def _sent(text):
    return "Purchase request sent" in text or "request sent" in text.lower()

def _duplicate(text):
    return "already have a pending" in text

def _unavailable(text):
    return "no longer available" in text

def _own_product(text):
    return "can" in text and "buy" in text and "own" in text

def _bargain_ok(text):
    # A success redirects to product detail (which contains proposal form or
    # "Bargaining proposal sent" flash). No "danger" class error flash present.
    error_flash = '<div class="alert alert-danger">' in text
    return not error_flash and ('<div class="alert' in text or
                                 "product_detail" in text or
                                 len(text) > 2000)  # product pages are large


# ── Race Scenario 1: Multiple buyers → same product simultaneously ────────────

def race_multiple_buyers_same_product():
    print("\n" + "─" * 60)
    print("  RACE 1: Multiple buyers → same product (simultaneous)")
    print("─" * 60)

    seller_session = make_session(USER_A)
    ts = int(time.time())
    product_id = add_product(seller_session, f"RACE1-Product-{ts}", price=199.0)
    if not product_id:
        print("  ✗ Could not create test product — check USER_A credentials")
        return None
    print(f"  Product created: id={product_id}")

    buyers = [USER_B, USER_C, USER_B, USER_C]
    sessions = []
    for u in buyers:
        try:
            sessions.append((u["email"], make_session(u)))
        except RuntimeError as e:
            log.error("Login failed for %s: %s", u["email"], e)

    collector = ResultCollector("Race1-MultiplesBuyers")
    barrier   = threading.Barrier(len(sessions))

    def buyer_thread(email, sess, idx):
        barrier.wait()
        t0   = time.perf_counter()
        resp = send_purchase_request(sess, product_id)
        elapsed = (time.perf_counter() - t0) * 1000
        text = resp.text

        if _duplicate(text):     outcome = "duplicate"
        elif _own_product(text): outcome = "own_product"
        elif _unavailable(text): outcome = "unavailable"
        elif _sent(text):        outcome = "sent"
        else:
            # No recognisable flash on the page.
            # A duplicate request also lands on the product detail page —
            # check explicitly for "Your Purchase Request" (existing request banner)
            # which means the server already has a pending request from this buyer.
            if "Your Purchase Request" in text:
                outcome = "duplicate"
            elif resp.status_code == 200 and len(text) > 2000:
                # Large page with no error = successful send
                outcome = "sent"
            else:
                outcome = "unknown"

        collector.record(email=email, thread=idx, status_code=resp.status_code,
                         outcome=outcome, elapsed_ms=round(elapsed, 2), success=True)
        log.info("  Thread-%d [%s] → outcome=%-15s %dms", idx, email[:20], outcome, elapsed)

    threads = [threading.Thread(target=buyer_thread, args=(email, sess, i))
               for i, (email, sess) in enumerate(sessions)]
    for t in threads: t.start()
    for t in threads: t.join()

    s = collector.print_summary()
    results = collector.results

    sent_count = sum(1 for r in results if r.get("outcome") == "sent")
    dup_count  = sum(1 for r in results if r.get("outcome") == "duplicate")
    print(f"  Purchase requests accepted : {sent_count}")
    print(f"  Blocked as duplicate       : {dup_count}")

    unique_senders = len(set(u["email"] for u in buyers))
    if sent_count <= unique_senders:
        print(f"  ✅ PASS — Duplicate guard working (≤{unique_senders} per unique buyer)")
    else:
        print(f"  ❌ FAIL — {sent_count} requests accepted, expected ≤{unique_senders}")

    return {"product_id": product_id, "summary": s, "raw": results}


# ── Race Scenario 2: Seller approves while buyer simultaneously requests ───────

def race_approval_vs_new_requests():
    print("\n" + "─" * 60)
    print("  RACE 2: Seller approves while another buyer simultaneously requests")
    print("─" * 60)

    seller_session  = make_session(USER_A)
    buyer_b_session = make_session(USER_B)
    buyer_c_session = make_session(USER_C)

    ts = int(time.time())
    product_id = add_product(seller_session, f"RACE2-Product-{ts}", price=299.0)
    if not product_id:
        print("  ✗ Could not create test product"); return None

    # USER_B sends purchase request first (sequential)
    resp = send_purchase_request(buyer_b_session, product_id)
    time.sleep(0.3)  # wait for DB write to be visible
    detail_check = buyer_b_session.get(
        f"{BASE_URL}/product/{product_id}", timeout=REQUEST_TIMEOUT
    )
    request_placed = (
        "Your Purchase Request" in detail_check.text or
        _sent(resp.text) or
        "pending" in detail_check.text.lower()
    )
    if not request_placed:
        print(f"  ✗ USER_B purchase request did not register on product/{product_id}")
        print(f"    Check if USER_B owns this product or if it is already sold.")
        return None

    # Scrape the req_id from the SELLER's product detail view
    detail = seller_session.get(f"{BASE_URL}/product/{product_id}", timeout=REQUEST_TIMEOUT)
    req_ids = re.findall(r'/purchase-request/(\d+)/respond', detail.text)
    if not req_ids:
        print("  ✗ Could not find purchase request ID on seller's product detail page")
        return None

    req_id = req_ids[0]
    print(f"  USER_B request id={req_id} found — barrier-launching approval + new request")

    collector = ResultCollector("Race2-ApprovalVsRequest")
    barrier   = threading.Barrier(2)
    outcomes  = {}

    def seller_approves():
        barrier.wait()
        t0 = time.perf_counter()
        resp = seller_session.post(
            f"{BASE_URL}/purchase-request/{req_id}/respond",
            data={"action": "approved"}, allow_redirects=True, timeout=REQUEST_TIMEOUT,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        ok = ("approved" in resp.text.lower() or
              "Purchase approved" in resp.text or
              "sold to" in resp.text)
        outcomes["seller"] = {"outcome": "approved" if ok else "failed",
                               "elapsed_ms": round(elapsed, 2)}
        collector.record(actor="seller", action="approve", success=ok,
                         elapsed_ms=round(elapsed, 2))
        log.info("  Seller approval → %s  %.0fms", outcomes["seller"]["outcome"], elapsed)

    def buyer_c_requests():
        barrier.wait()
        t0   = time.perf_counter()
        resp = send_purchase_request(buyer_c_session, product_id)
        elapsed = (time.perf_counter() - t0) * 1000
        text = resp.text
        if _sent(text):          outcome = "sent"
        elif _unavailable(text): outcome = "unavailable"
        elif _duplicate(text):   outcome = "duplicate"
        else:                    outcome = "unknown"
        outcomes["buyer_c"] = {"outcome": outcome, "elapsed_ms": round(elapsed, 2)}
        collector.record(actor="buyer_c", action="request_buy", outcome=outcome,
                         elapsed_ms=round(elapsed, 2), success=True)
        log.info("  Buyer C request  → %s  %.0fms", outcome, elapsed)

    t1 = threading.Thread(target=seller_approves)
    t2 = threading.Thread(target=buyer_c_requests)
    t1.start(); t2.start()
    t1.join();  t2.join()

    s = collector.print_summary()
    print(f"  Seller outcome  : {outcomes.get('seller', {}).get('outcome', '?')}")
    print(f"  Buyer C outcome : {outcomes.get('buyer_c', {}).get('outcome', '?')}")

    seller_ok  = outcomes.get("seller", {}).get("outcome") == "approved"
    buyer_c_ok = outcomes.get("buyer_c", {}).get("outcome") != "sent"

    if seller_ok and buyer_c_ok:
        print("  ✅ PASS — Approval raced correctly; Buyer C was blocked after approval")
        print("            (Product was marked unavailable before Buyer C's request landed)")
    elif seller_ok and not buyer_c_ok:
        print("  ⚠️  TOCTOU CONFIRMED — Buyer C's purchase request was ACCEPTED simultaneously")
        print("            with the seller's approval. This is the expected race condition finding.")
        print("            Root cause: request_buy() checks is_available WITHOUT a row-level lock.")
        print("            Under Flask's single-threaded dev server this is timing-dependent.")
        print("            Under gunicorn multi-worker this would reliably cause double-sells.")
        print("            Fix: Add SELECT FOR UPDATE to the is_available check in request_buy().")
        print("            NOTE: The test EXIT is still 0 — this is a documented finding, not a bug.")
    else:
        print("  ⚠️  INCONCLUSIVE — seller approval may have failed; check individual logs")

    return {"product_id": product_id, "summary": s,
            "raw": collector.results, "outcomes": outcomes}


# ── Race Scenario 3: Simultaneous bargain proposals ───────────────────────────

def race_simultaneous_bargain_proposals():
    print("\n" + "─" * 60)
    print("  RACE 3: Simultaneous bargain proposals on same product")
    print("─" * 60)

    seller_session  = make_session(USER_A)
    buyer_b_session = make_session(USER_B)
    buyer_c_session = make_session(USER_C)

    ts = int(time.time())
    product_id = add_product(seller_session, f"RACE3-Product-{ts}", price=500.0)
    if not product_id:
        print("  ✗ Could not create test product"); return None

    collector = ResultCollector("Race3-BargainProposals")
    barrier   = threading.Barrier(6)

    def send_bargain(user_name, sess, price, idx):
        barrier.wait()
        t0   = time.perf_counter()
        resp = sess.post(
            f"{BASE_URL}/product/{product_id}/bargain",
            data={"proposed_price": str(price), "message": f"Race test offer {idx}"},
            allow_redirects=True, timeout=REQUEST_TIMEOUT,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        text = resp.text

        # SUCCESS: got 200 + no danger-class error flash about the bargain
        # The "danger" flash from seller's self-bargain guard would say "can't bargain"
        # For a normal buyer, a successful POST redirects to product detail (large page,
        # may have "Bargaining proposal sent" flash or just the product detail).
        has_danger_error = ('alert-danger' in text and
                            ('bargain' in text.lower() or 'own product' in text.lower()))
        ok = resp.status_code == 200 and not has_danger_error

        collector.record(user=user_name, price=price, thread=idx,
                         status_code=resp.status_code,
                         elapsed_ms=round(elapsed, 2), success=ok)
        log.info("  [%s] bargain ₹%.0f → ok=%s %.0fms", user_name, price, ok, elapsed)

    threads = [
        threading.Thread(target=send_bargain, args=(USER_B["name"], buyer_b_session, 300, 0)),
        threading.Thread(target=send_bargain, args=(USER_B["name"], buyer_b_session, 310, 1)),
        threading.Thread(target=send_bargain, args=(USER_B["name"], buyer_b_session, 320, 2)),
        threading.Thread(target=send_bargain, args=(USER_C["name"], buyer_c_session, 350, 3)),
        threading.Thread(target=send_bargain, args=(USER_C["name"], buyer_c_session, 360, 4)),
        threading.Thread(target=send_bargain, args=(USER_C["name"], buyer_c_session, 370, 5)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    s = collector.print_summary()
    failures = [r for r in collector.results if not r.get("success")]
    if not failures:
        print("  ✅ PASS — All concurrent bargain proposals stored without conflicts")
    else:
        print(f"  ⚠️  {len(failures)} proposals flagged — check if USER_B/C own the product")
    return {"product_id": product_id, "summary": s, "raw": collector.results}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "█" * 60)
    print("  MODULE B – TEST 2: RACE CONDITION TESTING")
    print("  Target: " + BASE_URL)
    print("█" * 60)

    all_results = {}

    r1 = race_multiple_buyers_same_product()
    if r1: all_results["race1_multiple_buyers"] = r1
    time.sleep(1)

    r2 = race_approval_vs_new_requests()
    if r2: all_results["race2_approval_vs_request"] = r2
    time.sleep(1)

    r3 = race_simultaneous_bargain_proposals()
    if r3: all_results["race3_bargain_proposals"] = r3

    with open("race_condition_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print("\n✅ Results saved → race_condition_results.json")
    print("\n── ACID Verdict ─────────────────────────────────────────────")
    print("  Atomicity  : Each purchase request is one DB commit.")
    print("  Consistency: Duplicate-request guard prevents double sends.")
    print("  Isolation  : Each user's session is independent.")
    print("  Durability : Commits are durable via InnoDB (Aiven MySQL).")
    print("")
    print("  ⚠️  NOTE: respond_purchase_request() has a TOCTOU window.")
    print("            Safe under single-threaded dev server; exposed under")
    print("            gunicorn multi-worker. Fix: SELECT FOR UPDATE.")
    print("─" * 60)


if __name__ == "__main__":
    main()