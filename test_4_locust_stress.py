# =============================================================================
# test_4_locust_stress.py
# Module B – Stress Testing with Locust
#
# WHAT THIS TESTS:
#   Sends hundreds of simultaneous requests to measure:
#     • Response time (avg, p95, p99)
#     • Throughput (requests/second)
#     • Error rate under load
#     • System stability over time
#
# HOW TO RUN:
#   Option A – Headless (recommended for demo video):
#     locust -f test_4_locust_stress.py \
#            --headless \
#            --users 50 \
#            --spawn-rate 10 \
#            --run-time 60s \
#            --host http://localhost:5000 \
#            --csv stress_results \
#            --html stress_report.html
#
#   Option B – Web UI (interactive):
#     locust -f test_4_locust_stress.py --host http://localhost:5000
#     → open http://localhost:8089 in your browser
#
# INSTALL:
#   pip install locust
#
# OUTPUT:
#   stress_results_stats.csv     — per-endpoint stats
#   stress_results_failures.csv  — failed requests
#   stress_report.html           — full visual report
# =============================================================================

import random
import time
from locust import HttpUser, task, between, events
from config import USER_A, USER_B, USER_C, ALL_USERS


# ── Global shared state (populated at startup) ────────────────────────────────
_product_ids = []     # product IDs scraped from marketplace
_user_pool   = [USER_A, USER_B, USER_C]


# ── Event hooks ───────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Before the load test begins, log in as USER_A and scrape product IDs
    so tasks have real IDs to work with.
    """
    import requests, re
    s = requests.Session()
    try:
        s.get(f"{environment.host}/login", timeout=10)
        r = s.post(f"{environment.host}/login",
                   data={"email": USER_A["email"], "password": USER_A["password"]},
                   allow_redirects=True, timeout=10)
        marketplace = s.get(f"{environment.host}/marketplace", timeout=10)
        ids = list(set(re.findall(r'/product/(\d+)', marketplace.text)))
        _product_ids.extend([int(i) for i in ids[:20]])   # take up to 20
        print(f"\n[Locust] Warmed up — found {len(_product_ids)} products: {_product_ids[:5]}...")
    except Exception as e:
        print(f"\n[Locust] Warmup failed: {e}")


# ── User Behaviour Classes ────────────────────────────────────────────────────

class BrowsingUser(HttpUser):
    """
    Simulates a read-heavy user: browsing marketplace, viewing products,
    checking notifications. This is the most common real-world user pattern.
    Weight=3 means 3x more of these users than WritingUser.
    """
    weight      = 3
    wait_time   = between(0.5, 2.0)   # realistic think-time between requests
    _session_ok = False
    _user       = None

    def on_start(self):
        """Log in once when this virtual user starts."""
        self._user = random.choice(_user_pool)
        # GET login page (gets session cookie)
        self.client.get("/login", name="/login [GET]")
        resp = self.client.post(
            "/login",
            data={"email": self._user["email"], "password": self._user["password"]},
            allow_redirects=True,
            name="/login [POST]",
        )
        self._session_ok = "/login" not in resp.url
        if not self._session_ok:
            print(f"[Locust] WARNING: Login failed for {self._user['email']}")

    @task(5)
    def browse_marketplace(self):
        """Most frequent action: view the marketplace listing."""
        self.client.get("/marketplace", name="/marketplace")

    @task(3)
    def marketplace_filter_category(self):
        """Filter marketplace by category."""
        cat = random.choice(["Books", "Electronics", "Clothing", "Stationery", "Sports"])
        self.client.get(f"/marketplace?category={cat}", name="/marketplace?category=[cat]")

    @task(2)
    def marketplace_search(self):
        """Search the marketplace."""
        term = random.choice(["book", "phone", "pen", "bag", "notes"])
        self.client.get(f"/marketplace?search={term}", name="/marketplace?search=[term]")

    @task(2)
    def marketplace_price_filter(self):
        """Filter by price range."""
        lo = random.randint(10, 100)
        hi = lo + random.randint(100, 500)
        self.client.get(
            f"/marketplace?min_price={lo}&max_price={hi}",
            name="/marketplace?price=[range]",
        )

    @task(4)
    def view_product_detail(self):
        """View a specific product page."""
        if _product_ids:
            pid = random.choice(_product_ids)
            self.client.get(f"/product/{pid}", name="/product/[id]")

    @task(1)
    def view_transactions(self):
        """Check transaction history."""
        self.client.get("/transactions", name="/transactions")

    @task(1)
    def view_notifications(self):
        """Check notifications."""
        self.client.get("/notifications", name="/notifications")

    @task(1)
    def view_demands(self):
        """Browse demands page."""
        self.client.get("/demands", name="/demands")


class WritingUser(HttpUser):
    """
    Simulates a write-heavy user: adding products, sending bargain proposals,
    submitting purchase requests. Less common but more DB-intensive.
    Weight=1 means 1x fewer of these.
    """
    weight      = 1
    wait_time   = between(1.0, 3.0)
    _session_ok = False
    _user       = None
    _my_product = None

    def on_start(self):
        self._user = random.choice([USER_B, USER_C])
        self.client.get("/login", name="/login [GET]")
        resp = self.client.post(
            "/login",
            data={"email": self._user["email"], "password": self._user["password"]},
            allow_redirects=True,
            name="/login [POST]",
        )
        self._session_ok = "/login" not in resp.url

    @task(3)
    def add_product_listing(self):
        """Add a product to the marketplace."""
        ts = int(time.time() * 1000) % 100000
        self.client.post(
            "/product/add",
            data={
                "title":       f"StressTest-{ts}",
                "description": "Locust stress test product",
                "price":       str(random.randint(10, 500)),
                "category":    random.choice(["Books", "Electronics", "Clothing"]),
                "condition":   random.choice(["New", "Good", "Fair"]),
            },
            allow_redirects=True,
            name="/product/add [POST]",
        )

    @task(2)
    def send_bargain_proposal(self):
        """Send a bargain proposal on a random product."""
        if _product_ids:
            pid   = random.choice(_product_ids)
            price = random.randint(50, 400)
            self.client.post(
                f"/product/{pid}/bargain",
                data={"proposed_price": str(price), "message": "Stress test offer"},
                allow_redirects=True,
                name="/product/[id]/bargain [POST]",
            )

    @task(1)
    def request_to_buy(self):
        """Send a purchase request for a random product."""
        if _product_ids:
            pid = random.choice(_product_ids)
            self.client.post(
                f"/product/{pid}/request-buy",
                data={"buy_message": "Stress test purchase request"},
                allow_redirects=True,
                name="/product/[id]/request-buy [POST]",
            )

    @task(1)
    def submit_review(self):
        """Submit a review on a product."""
        if _product_ids:
            pid    = random.choice(_product_ids)
            rating = random.randint(1, 5)
            self.client.post(
                f"/product/{pid}/review",
                data={"rating": str(rating), "comment": "Stress test review"},
                allow_redirects=True,
                name="/product/[id]/review [POST]",
            )


class AdminUser(HttpUser):
    """
    Simulates an admin checking logs and member lists.
    Very low weight — only 1 admin-type user in the mix.
    """
    weight    = 0   # Set to 1 if you have admin credentials configured
    wait_time = between(2.0, 5.0)

    def on_start(self):
        # Log in as admin — add admin credentials to config.py if needed
        self.client.post(
            "/login",
            data={"email": USER_A["email"], "password": USER_A["password"]},
            allow_redirects=True,
            name="/login [POST]",
        )

    @task(1)
    def view_admin_logs(self):
        self.client.get("/admin/logs", name="/admin/logs")
