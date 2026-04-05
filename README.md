# Module B — High-Concurrency API Load Testing & Failure Simulation

> **CS 432 Databases — Assignment 3**
> Campus Trading Application 

---

## Project Overview

This is a Flask-based campus trading web application that allows students to list, browse, and purchase second-hand items. The system uses Flask-SQLAlchemy with a MySQL backend (via PyMySQL). Module B validates that the system behaves correctly under simultaneous multi-user load by simulating concurrent access patterns, race conditions, intentional failure injection, stress testing, and formal ACID verification.

---

## What is Module B?

Module B — *High-Concurrency API Load Testing & Failure Simulation* — verifies that the application works safely when many users interact with it at the same time. Specifically, it:

- Simulates multiple users performing operations simultaneously
- Tests that concurrent access to shared resources (e.g., the same product listing) does not produce incorrect or inconsistent results
- Identifies and documents race conditions (e.g., two buyers trying to purchase the same item simultaneously)
- Injects failures (invalid inputs, bad auth, connection aborts) to verify correct rejection and rollback
- Stress tests the system under hundreds of requests to measure throughput, response time, and error rate
- Formally verifies all four ACID properties through targeted experimental checks

---

## Module B Implementation in This Codebase

### Multi-User Concurrency Handling

Concurrent usage is simulated using Python's `threading` module. Each test script spawns multiple `threading.Thread` instances — one per simulated user — each maintaining its own independent HTTP session via the `requests.Session` object.

Session isolation is achieved naturally: each thread logs in with a distinct user credential before the test begins, receives its own session cookie from Flask, and all subsequent requests in that thread use only that cookie. This maps directly to real multi-user scenarios.

**File:** `test_1_concurrency.py`

- **Scenario 1 (Concurrent Reads):** 3 users × 3 worker types (marketplace browse, transaction view, product detail view) = 9 threads firing simultaneously for 5 iterations each — 45 total requests executed in parallel. Results showed 45/45 successes with wall-clock time of 17.32s (versus ~92s sequential), confirming the Flask server handles parallel reads correctly.
- **Scenario 2 (Concurrent Writes):** 6 threads attempt to add products simultaneously. All 6 succeeded, confirming the database handles concurrent inserts without corruption.

### Threading / Async / API Behavior

- **Synchronization primitive:** `threading.Barrier` is used in race condition tests to ensure all threads release simultaneously (true simultaneous requests), not in a staggered fashion. A barrier waits until all `N` threads call `.wait()`, then releases them all at once.
- **Session creation:** The `make_session(user)` helper (in `app/helpers.py`) performs a login POST and returns an authenticated `requests.Session` ready for use.
- **Request timing:** `time.perf_counter()` is used for high-resolution elapsed-time measurement on each request, logged per-thread in JSON result files.

### Race Condition Handling

**File:** `test_2_race_conditions.py`

Three race scenarios are tested:

**Race 1 — Multiple buyers → same product:**
Four buyer threads (USER_B and USER_C, each twice) are barrier-synchronized and simultaneously submit purchase requests for the same product. The expected behavior is that each unique buyer gets at most one accepted request, and duplicate submissions are blocked. The application-level duplicate guard in `request_buy()` checks for an existing `PurchaseRequest` with `status='pending'` before inserting a new one.

**Race 2 — Seller approves while a new buyer simultaneously requests:**
A `threading.Barrier(2)` synchronizes the seller approval thread and a new buyer request thread to fire at exactly the same moment. The `respond_purchase_request()` route uses `SELECT FOR UPDATE` (`db.session.query(...).with_for_update()`) on both the `PurchaseRequest` and `Product` rows, serializing concurrent approvals at the database level. This eliminates the TOCTOU (Time-of-Check to Time-of-Use) window that would otherwise allow double-sells under a multi-worker deployment.

**Race 3 — Simultaneous bargain proposals:**
Six threads (3 from USER_B, 3 from USER_C) simultaneously submit bargain proposals on the same product using a `threading.Barrier(6)`. Since proposals are independent insert operations (not guarded by a shared resource), all are expected to succeed without conflict.

### Failure Simulation Logic

**File:** `test_3_failure_simulation.py`

Five categories of failure injection are tested:

1. **Invalid product data:** Empty title, empty price, negative price, non-numeric price — all must be rejected by Flask-side validation. Zero price, no category, huge price values, SQL injection in title, and XSS in title are intentionally accepted (by design) because SQLAlchemy parameterizes queries and Jinja2 auto-escapes output.
2. **Purchase request edge cases:** Self-buy attempt (rejected by business logic), purchase of a non-existent product (rejected by `get_or_404`), and duplicate purchase request (rejected by the pending-request guard).
3. **Review failures:** Out-of-range rating values (0, 6, -1, `abc`, empty string) — all rejected by the `int(rating)` validation with range check.
4. **Auth failures:** Wrong password, empty email, empty password, malformed email, SQL injection in email fields — all result in redirect back to `/login` (no session granted).
5. **Connection abort simulation:** A 50ms timeout is forced on a `POST /bargain` request, simulating a mid-flight client disconnect. After the abort, a `GET` on the product page confirms the server state remains consistent (HTTP 200, no partial write).

### Stress Testing Approach

**File:** `test_4_locust_stress.py`

Locust is used for HTTP-level stress testing. Two `HttpUser` subclasses are defined:

- `BrowsingUser` (weight=3): simulates read-heavy users — marketplace browsing, product detail views, notification polling. Think time is `between(0.5, 2.0)` seconds.
- `WritingUser` (weight=1): simulates write-heavy users — adding products, sending purchase requests, submitting bargain proposals.

The `@events.test_start` hook pre-warms the test by logging in as USER_A and scraping up to 20 real product IDs from the marketplace, so task functions have valid IDs to work with.

**Recommended run command:**
```bash
locust -f test_4_locust_stress.py \
       --headless \
       --users 50 \
       --spawn-rate 10 \
       --run-time 60s \
       --host http://localhost:5000 \
       --csv stress_results \
       --html stress_report.html
```

---

## How to Run Module B

### Setup Steps

```bash
# 1. Clone the repository and enter the project directory
cd final_app

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate        # Linux/macOS


# 3. Install dependencies
pip install -r requirements.txt
pip install locust               # for stress testing only

# 4. Configure environment
cp .env.example .env             # fill in DB credentials

# 5. Configure test users in config.py
#    Set BASE_URL, USER_A, USER_B, USER_C with valid credentials

# 6. Start the Flask application (in a separate terminal)
python app.py
```

### Commands to Run Concurrency Tests

```bash
# Test 1: Concurrent multi-user reads and writes
python test_1_concurrency.py
# Output: concurrency_results.json

# Test 2: Race condition testing (barrier-synchronized threads)
python test_2_race_conditions.py
# Output: race_condition_results.json

# Test 3: Failure injection and rollback verification
python test_3_failure_simulation.py
# Output: failure_simulation_results.json

# Test 4: Stress testing with Locust (headless)
locust -f test_4_locust_stress.py \
       --headless --users 50 --spawn-rate 10 \
       --run-time 60s --host http://localhost:5000 \
       --csv stress_results --html stress_report.html

# Test 5: ACID property verification
python test_5_acid_verification.py
# Output: acid_verification_results.json

# Run all tests sequentially
python run_all_tests.py
```

---

## Technologies Used

| Component | Technology |
|---|---|
| Web framework | Flask 3.1.0 |
| ORM | Flask-SQLAlchemy 3.1.1 / SQLAlchemy 2.0.x |
| Database | MySQL (via PyMySQL 1.1.1) |
| Concurrency testing | Python `threading` (stdlib) |
| HTTP client | `requests` (with session persistence) |
| Stress testing | Locust |
| Password hashing | Flask-Bcrypt 1.0.1 |
| Environment config | python-dotenv 1.0.1 |

---

## Observations

- **Concurrent reads (45 requests):** 100% success rate, 0 failures. Average response time ~2056ms, wall-clock time 17.32s (parallelism factor ~5x over sequential).
- **Concurrent writes (6 simultaneous product additions):** 100% success, no data corruption observed.
- **Race condition guard:** `SELECT FOR UPDATE` on `PurchaseRequest` and `Product` rows in `respond_purchase_request()` serializes concurrent approvals at the DB level, preventing double-sell under multi-worker deployments.
- **Failure injection:** All mandatory validation failures (negative price, invalid rating, self-buy, duplicate request, bad auth) were correctly rejected. SQL injection and XSS inputs were safely stored as literal text.
- **ACID verification:** All 13 checks across Atomicity (3/3), Consistency (4/4), Isolation (3/3), and Durability (3/3) passed.

---

## Limitations

- The Flask development server is single-threaded by default. True concurrent request interleaving only occurs under a multi-worker deployment (e.g., `gunicorn --workers 4`). Tests were run against the dev server, so some race conditions are timing-dependent and may not manifest reliably in this configuration.
- Locust stress test results (response times, throughput) depend heavily on the host machine's resources and the MySQL server location (local vs. remote Aiven). Reported numbers reflect the development environment only.
- No distributed load testing was performed (all threads originate from a single machine). Production-grade testing would require a distributed Locust setup.
- The `SELECT FOR UPDATE` fix in `respond_purchase_request()` requires InnoDB (row-level locking). If the MySQL table uses a non-InnoDB storage engine, the lock will not function as expected.
- Test user credentials in `config.py` are placeholders and must be replaced with valid database entries before running.
