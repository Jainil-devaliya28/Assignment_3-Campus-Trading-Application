# =============================================================================
# helpers.py  –  Shared utilities for Flask app and Module B test scripts
# =============================================================================
from functools import wraps
from flask import session, redirect, url_for, flash, abort
from app.models import db, Log, Notification
import requests
import logging
import json
import time
from config import BASE_URL, REQUEST_TIMEOUT

# ── Flask App Helpers ─────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'member_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'member_id' not in session or session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def log_action(action_type: str, description: str, member_id: int = None):
    """Log an action to the database."""
    try:
        if member_id is None:
            member_id = session.get('member_id')
        entry = Log(member_id=member_id, action_type=action_type, description=description)
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        print(f"Logging failed: {e}")

def log_security_event(event_type: str, description: str, ip: str = None, member_id: int = None):
    """Log a security event."""
    full_desc = f"{description} | IP: {ip}" if ip else description
    log_action(f"SECURITY_{event_type}", full_desc, member_id)

def notify(member_id: int, message: str, title: str = 'Notification', link: str = None, notification_type: str = 'info'):
    """Send a notification to a member."""
    try:
        notif = Notification(
            member_id=member_id,
            title=title,
            message=message,
            link=link,
        )
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Notification failed: {e}")

# ── Test Helpers ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("campus_test")


# ── Session / Auth ────────────────────────────────────────────────────────────

def make_session(user: dict) -> requests.Session:
    """
    Create an authenticated requests.Session for a given user dict.
    Returns the session on success, raises RuntimeError on failure.
    """
    s = requests.Session()
    s.headers.update({"User-Agent": "CampusTest/1.0"})

    max_retries = 10
    for attempt in range(max_retries):
        try:
            # GET the login page first to grab any CSRF token / cookies
            resp = s.get(f"{BASE_URL}/login", timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                log.warning("Server not ready, retrying in 2s... (%d/%d)", attempt + 1, max_retries)
                time.sleep(2)
            else:
                raise RuntimeError(f"Server not accessible at {BASE_URL}/login after {max_retries} attempts: {e}")

    # POST credentials
    resp = s.post(
        f"{BASE_URL}/login",
        data={"email": user["email"], "password": user["password"]},
        allow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    )

    # Flask redirects to /dashboard on success; login page stays on failure
    if "/login" in resp.url and "Invalid" in resp.text:
        raise RuntimeError(f"Login FAILED for {user['email']} — check credentials in config.py")

    log.info("✓ Logged in as %s", user["email"])
    return s


def logout(session: requests.Session) -> None:
    try:
        session.get(f"{BASE_URL}/logout", timeout=REQUEST_TIMEOUT)
    except Exception:
        pass


# ── Product Helpers ───────────────────────────────────────────────────────────

def add_product(session: requests.Session, title: str, price: float = 99.0) -> int | None:
    """
    Add a product as the logged-in user.
    Returns product_id (int) on success, None on failure.

    Strategy: POST to /product/add — on success the server redirects to
    /product/<id> (the product detail page). With allow_redirects=True,
    resp.url will be that URL, so we extract the ID directly from it.
    This is 100% reliable regardless of how many products exist in the DB.
    """
    import re as _re

    resp = session.post(
        f"{BASE_URL}/product/add",
        data={
            "title":       title,
            "description": "Module B test product — safe to delete",
            "price":       str(price),
            "category":    "Books",
            "condition":   "Good",
        },
        allow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    )

    if resp.status_code != 200:
        log.warning("x add_product POST failed (status=%d)", resp.status_code)
        return None

    # Extract product_id from the final redirect URL: /product/<id>
    m = _re.search(r'/product/(\d+)', resp.url)
    if m:
        pid = int(m.group(1))
        log.info("✓ Created product '%s' → id=%d", title, pid)
        return pid

    log.warning("x add_product: final URL '%s' has no product id", resp.url)
    return None


def get_available_products(session: requests.Session) -> list[dict]:
    """Return list of {id, title} for all available products on the marketplace."""
    import re
    resp = session.get(f"{BASE_URL}/marketplace", timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        return []
    # Scrape product IDs and titles from the page
    ids     = re.findall(r'/product/(\d+)', resp.text)
    titles  = re.findall(r'<h5[^>]*>(.*?)</h5>', resp.text)
    # Deduplicate ids preserving order
    seen, products = set(), []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            products.append({"id": int(pid)})
    return products


def send_purchase_request(session: requests.Session, product_id: int) -> requests.Response:
    return session.post(
        f"{BASE_URL}/product/{product_id}/request-buy",
        data={"buy_message": "Race condition test — automated"},
        allow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    )


# ── Result Tracking ───────────────────────────────────────────────────────────

class ResultCollector:
    """Thread-safe collector for test results."""

    def __init__(self, test_name: str):
        import threading
        self.test_name  = test_name
        self.lock       = threading.Lock()
        self.results    = []   # list of dicts

    def record(self, **kwargs):
        with self.lock:
            self.results.append(kwargs)

    def summary(self) -> dict:
        if not self.results:
            return {
                "test": self.test_name,
                "total": 0,
                "successes": 0,
                "failures": 0,
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
            }
        successes   = [r for r in self.results if r.get("success")]
        failures    = [r for r in self.results if not r.get("success")]
        times       = [r["elapsed_ms"] for r in self.results if "elapsed_ms" in r]
        return {
            "test":         self.test_name,
            "total":        len(self.results),
            "successes":    len(successes),
            "failures":     len(failures),
            "avg_ms":       round(sum(times) / len(times), 1) if times else None,
            "min_ms":       round(min(times), 1) if times else None,
            "max_ms":       round(max(times), 1) if times else None,
        }

    def print_summary(self):
        s = self.summary()
        print("\n" + "=" * 60)
        print(f"  RESULTS: {s['test']}")
        print("=" * 60)
        print(f"  Total requests : {s['total']}")
        print(f"  Successes      : {s['successes']}")
        print(f"  Failures       : {s['failures']}")
        if s.get("avg_ms"):
            print(f"  Avg latency    : {s['avg_ms']} ms")
            print(f"  Min / Max      : {s['min_ms']} ms / {s['max_ms']} ms")
        print("=" * 60 + "\n")
        return s