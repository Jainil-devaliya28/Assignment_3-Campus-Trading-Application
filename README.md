# Module B — Multi-User Behaviour & Stress Testing
## Campus Trading Platform

---

## Quick Start (3 steps)

### Step 1 — Install dependencies
```bash
pip install requests locust reportlab
```

### Step 2 — Configure test users
Open `config.py` and fill in real credentials for 3 users in your DB:
```python
USER_A = { "email": "seller@example.com",  "password": "yourpassword" }
USER_B = { "email": "buyer1@example.com",  "password": "yourpassword" }
USER_C = { "email": "buyer2@example.com",  "password": "yourpassword" }
```
> **USER_A** will act as the seller (creates test products).  
> **USER_B** and **USER_C** will act as competing buyers.

### Step 3 — Start your Flask app, then run tests
```bash
# In one terminal:
cd campus_v3/final_app
python app.py          # or: flask run

# In another terminal (from the module_b_tests folder):
python run_all_tests.py
```

---

## Running Tests Individually

| Script | Command | What it does |
|--------|---------|--------------|
| Test 1 — Concurrency | `python test_1_concurrency.py` | 9 threads doing reads + writes simultaneously |
| Test 2 — Race Conditions | `python test_2_race_conditions.py` | Hammers purchase/approval with Barrier-sync threads |
| Test 3 — Failure Injection | `python test_3_failure_simulation.py` | 22 malformed/invalid requests; verifies rejection |
| Test 4 — Stress (Locust) | See below | 50 virtual users for 60 seconds |
| Test 5 — ACID | `python test_5_acid_verification.py` | Verifies all 4 ACID properties experimentally |
| Report | `python generate_report.py` | Generates Module_B_Report.pdf |

---

## Running the Locust Stress Test (Test 4)

### Headless mode (best for demo video):
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

### Web UI mode (interactive):
```bash
locust -f test_4_locust_stress.py --host http://localhost:5000
# Then open: http://localhost:8089
```

---

## Output Files

After running all tests, you will have:

| File | Contents |
|------|----------|
| `concurrency_results.json` | Thread timings, latencies, pass/fail |
| `race_condition_results.json` | Race scenario outcomes |
| `failure_simulation_results.json` | Injection results |
| `acid_verification_results.json` | ACID check results |
| `master_report.json` | Combined summary from run_all_tests.py |
| `stress_results_stats.csv` | Locust per-endpoint statistics |
| `stress_results_failures.csv` | Locust failed requests |
| `stress_report.html` | Locust HTML visual report |
| `Module_B_Report.pdf` | Submission report |

---

## Demo Video Sequence (recommended)

1. Show `config.py` with credentials filled in
2. Run `python test_1_concurrency.py` — show thread log output
3. Run `python test_2_race_conditions.py` — highlight RACE 1 and RACE 2 output
4. Run `python test_3_failure_simulation.py` — show ✅ rejection lines
5. Run `python test_5_acid_verification.py` — show all 4 ACID sections
6. Run Locust headless command — show RPS and latency in terminal
7. Open `stress_report.html` in browser — show the charts
8. Open `Module_B_Report.pdf` — briefly show ACID table and TOCTOU section

---

## Architecture Notes

| Component | Detail |
|-----------|--------|
| Backend | Python 3.13 / Flask 3.1 |
| ORM | Flask-SQLAlchemy 2.0 (scoped_session per request) |
| Database | MySQL 8 on Aiven Cloud (InnoDB — B+ Tree indexes) |
| Transactions | Implicit via db.session.commit() / rollback() in error handlers |
| Concurrency | Single-threaded dev server (serialised); safe for testing |
| Known vulnerability | TOCTOU in respond_purchase_request() — safe under single worker, exposed under gunicorn multi-worker |

---

## ACID Summary

| Property | How Verified | Result |
|----------|-------------|--------|
| **Atomicity** | Failed add → no partial record; Approval → txn+delist in one commit | ✅ PASS |
| **Consistency** | Dup email, self-buy, invalid price, bad rating all rejected | ✅ PASS |
| **Isolation** | Session cookies independent; concurrent reads non-interfering | ✅ PASS |
| **Durability** | Writes visible immediately from fresh sessions across network | ✅ PASS |
