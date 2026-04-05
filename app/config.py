import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///campus_trading.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True

# =============================================================================
# Module B – Test Configuration
# Campus Trading Platform
# =============================================================================
# INSTRUCTIONS:
#   1. Fill in real credentials for 3 existing users below.
#   2. USER_A should own (or be able to create) at least one product listing.
#   3. USER_B and USER_C will act as competing buyers.
#   4. Set BASE_URL to where your Flask app is running.
# =============================================================================

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

# ── Test Users ────────────────────────────────────────────────────────────────
# Replace with real credentials from your DB.
USER_A = {
    "email":    "usera@example.com",   # <-- REPLACE
    "password": "password123",          # <-- REPLACE
    "name":     "User A (Seller)",
}

USER_B = {
    "email":    "userb@example.com",   # <-- REPLACE
    "password": "password123",          # <-- REPLACE
    "name":     "User B (Buyer 1)",
}

USER_C = {
    "email":    "userc@example.com",   # <-- REPLACE
    "password": "password123",          # <-- REPLACE
    "name":     "User C (Buyer 2)",
}

ALL_USERS = [USER_A, USER_B, USER_C]

# ── Stress Test Settings ──────────────────────────────────────────────────────
STRESS_USERS        = 50     # concurrent Locust users
STRESS_SPAWN_RATE   = 10     # users spawned per second
STRESS_DURATION_SEC = 60     # total run duration

# ── Concurrency Test Settings ─────────────────────────────────────────────────
RACE_THREAD_COUNT   = 10     # threads hammering the same endpoint simultaneously
RACE_ITERATIONS     = 5      # how many rounds to repeat each race scenario

# ── Timeouts ─────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT     = 15     # seconds before a request is considered failed
