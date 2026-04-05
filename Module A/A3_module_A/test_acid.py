"""
ACID Validation Tests  –  Verbose / Narrative Edition
======================================================
Every test prints a live step-by-step story of what the engine is doing
so you can see exactly how each ACID guarantee is being enforced.

Run with:
    python -m pytest tests/test_acid.py -v -s
or directly (recommended for full output):
    python tests/test_acid.py
"""

import os
import sys
import tempfile
import unittest
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import DatabaseManager

WAL_PATH = os.path.join(tempfile.gettempdir(), "test_acid.wal")
W = 68   # box width


# ══════════════════════════════════════════════════════════════════════
# Pretty-print helpers
# ══════════════════════════════════════════════════════════════════════

def _banner(title):
    pad = max(0, W - len(title) - 2)
    print(f"\n{'═'*(pad//2)} {title} {'═'*(pad - pad//2)}")

def _section(title):
    print(f"\n  ┌── {title}")

def _step(msg, indent=4):
    prefix = " " * indent + "│  "
    for line in textwrap.wrap(msg, W - indent - 4):
        print(prefix + line)

def _result(label, value, good=True):
    icon = "✔" if good else "✘"
    print(f"  │  {icon}  {label}: {value}")

def _ok(msg):
    print(f"  └─ ✔  {msg}")

def _wal_snapshot(db):
    records = db._wal.get_records()
    if not records:
        _step("WAL is empty.")
        return
    _step(f"WAL now contains {len(records)} record(s):")
    for r in records:
        tbl = f" table={r.table_name}" if r.table_name else ""
        key = f" key={r.key}"          if r.key is not None else ""
        old = f" old={r.old_value}"    if r.old_value is not None else ""
        new = f" new={r.new_value}"    if r.new_value is not None else ""
        print(f"     LSN {r.lsn:>3} │ txn={r.txn_id} │ {r.record_type.value:<10}{tbl}{key}{old}{new}")

def _table_snapshot(db, table_name):
    table    = db.get_table(table_name)
    rec_keys = sorted(table.records.keys())
    idx_keys = sorted(k for k, _ in table.bplustree.get_all())
    _step(f"Table '{table_name}' records dict  : {rec_keys}")
    _step(f"Table '{table_name}' B+ Tree index : {idx_keys}")
    _step(f"Index ↔ Records in sync           : {'YES ✔' if rec_keys == idx_keys else 'NO ✘'}")


def fresh_db(name="testdb"):
    if os.path.exists(WAL_PATH):
        os.remove(WAL_PATH)
    db = DatabaseManager(name, log_path=WAL_PATH, auto_recover=False)
    db.create_table("users", "id", order=4)
    return db


# ══════════════════════════════════════════════════════════════════════
# ATOMICITY
# ══════════════════════════════════════════════════════════════════════

class TestAtomicity(unittest.TestCase):

    def test_successful_single_insert_commits(self):
        _banner("ATOMICITY  ·  successful single insert commits")
        _section("Setup")
        db = fresh_db()
        _step("Fresh database created. WAL is empty. Table 'users' has 0 rows.")
        _section("Action: insert key=1  →  {'id':1, 'name':'Alice'}  then COMMIT")
        _step("Step 1 · TransactionManager.begin() assigns txn_id=1, writes BEGIN to WAL.")
        _step("Step 2 · table.transactional_insert() writes INSERT(key=1) to WAL and immediately calls _raw_insert() so the row exists in memory.")
        _step("Step 3 · db_manager.commit() writes COMMIT to WAL then fsyncs to disk.")
        db.insert_record("users", 1, {"id": 1, "name": "Alice"})
        _wal_snapshot(db)
        _section("Verification")
        record = db.get_table("users").search(1)
        _result("search(1) returned", record)
        _result("record['name']", record["name"])
        _table_snapshot(db, "users")
        self.assertIsNotNone(record)
        self.assertEqual(record["name"], "Alice")
        _ok("INSERT committed → row is visible in both records dict and B+ Tree index.")

    def test_rollback_insert_leaves_no_trace(self):
        _banner("ATOMICITY  ·  rollback insert leaves no trace")
        _section("Setup")
        db = fresh_db()
        _step("Fresh database. Table 'users' is empty.")
        _section("Action: begin txn, insert key=99, then ROLLBACK (simulated failure)")
        _step("Step 1 · begin_transaction() → txn_id=1.")
        txn = db.begin_transaction()
        _step("Step 2 · transactional_insert(key=99) stages INSERT in WAL and calls _raw_insert() — row is temporarily in memory.")
        db.get_table("users").transactional_insert(txn, 99, {"id": 99, "name": "Ghost"})
        _step("Step 3 · Before commit, failure detected → db.rollback(txn).")
        _step("         Transaction.abort() iterates _ops in REVERSE and calls _raw_delete(99) to undo the insert. ABORT record written to WAL.")
        db.rollback(txn)
        _wal_snapshot(db)
        _section("Verification")
        search_result = db.get_table("users").search(99)
        in_records    = 99 in db.get_table("users").records
        in_index      = db.get_table("users").bplustree.search(99)
        _result("search(99) after rollback", search_result,  good=(search_result is None))
        _result("key 99 in records dict",    in_records,     good=(not in_records))
        _result("B+ Tree search(99)",        in_index,       good=(in_index is None))
        _table_snapshot(db, "users")
        self.assertIsNone(search_result)
        self.assertNotIn(99, db.get_table("users").records)
        self.assertIsNone(in_index)
        _ok("Rolled-back INSERT left zero trace in the database.")

    def test_rollback_update_restores_old_value(self):
        _banner("ATOMICITY  ·  rollback update restores old value")
        _section("Setup")
        db = fresh_db()
        db.insert_record("users", 2, {"id": 2, "name": "Bob"})
        _step("Committed row: key=2, name='Bob'.")
        _section("Action: update name to 'Robert', then ROLLBACK")
        _step("Step 1 · transactional_update() snapshots BEFORE-IMAGE {'name':'Bob'} into WAL record's old_value field.")
        _step("Step 2 · _raw_update() overwrites record in memory with 'Robert'.")
        txn = db.begin_transaction()
        db.get_table("users").transactional_update(txn, 2, {"id": 2, "name": "Robert"})
        _step("         (record is now 'Robert' in memory — txn NOT yet committed)")
        _step("Step 3 · rollback() → abort() finds UPDATE op, reads old_value='Bob', calls _raw_update(key=2, old_record) to restore original data.")
        db.rollback(txn)
        _wal_snapshot(db)
        _section("Verification")
        record = db.get_table("users").search(2)
        _result("record['name'] after rollback", record["name"])
        _table_snapshot(db, "users")
        self.assertEqual(record["name"], "Bob")
        _ok("Before-image correctly restored: 'Robert' → 'Bob'.")

    def test_rollback_delete_restores_row(self):
        _banner("ATOMICITY  ·  rollback delete restores the row")
        _section("Setup")
        db = fresh_db()
        db.insert_record("users", 3, {"id": 3, "name": "Carol"})
        _step("Committed row: key=3, name='Carol'.")
        _section("Action: delete key=3, then ROLLBACK")
        _step("Step 1 · transactional_delete() captures BEFORE-IMAGE {'name':'Carol'} as old_value in the WAL DELETE record.")
        _step("Step 2 · _raw_delete() removes the row from records dict AND B+ Tree.")
        txn = db.begin_transaction()
        db.get_table("users").transactional_delete(txn, 3)
        _step(f"         (row temporarily gone: search(3) = {db.get_table('users').search(3)})")
        _step("Step 3 · rollback() → abort() finds DELETE op, reads old_value, calls _raw_insert(key=3, old_record) to re-insert the row.")
        db.rollback(txn)
        _wal_snapshot(db)
        _section("Verification")
        record = db.get_table("users").search(3)
        _result("search(3) after rollback", record,            good=(record is not None))
        _result("record['name']",           record["name"] if record else "—")
        _table_snapshot(db, "users")
        self.assertIsNotNone(record)
        self.assertEqual(record["name"], "Carol")
        _ok("Deleted row fully restored by rollback.")

    def test_multi_op_transaction_rolls_back_completely(self):
        _banner("ATOMICITY  ·  multi-op transaction rolls back ALL ops")
        _section("Setup")
        db = fresh_db()
        db.insert_record("users", 10, {"id": 10, "name": "Dave"})
        _step("Committed row: key=10, name='Dave'.")
        _section("Action: begin txn with 2 ops (insert key=11 + update key=10), ROLLBACK")
        txn   = db.begin_transaction()
        table = db.get_table("users")
        _step("Op 1 · transactional_insert(key=11, name='Eve') → staged in WAL.")
        table.transactional_insert(txn, 11, {"id": 11, "name": "Eve"})
        _step("Op 2 · transactional_update(key=10, name='David') → before-image 'Dave' saved.")
        table.transactional_update(txn, 10, {"id": 10, "name": "David"})
        _step("         In-memory state now: key=10→'David', key=11→'Eve'.")
        _step("ROLLBACK called → abort() processes ops in REVERSE order:")
        _step("  undo Op2 (UPDATE): restore key=10 to 'Dave' via before-image.")
        _step("  undo Op1 (INSERT): delete key=11 (it never should have existed).")
        db.rollback(txn)
        _wal_snapshot(db)
        _section("Verification")
        dave = table.search(10)
        eve  = table.search(11)
        _result("key=10 name after rollback", dave["name"] if dave else "—")
        _result("key=11 exists after rollback", eve, good=(eve is None))
        _table_snapshot(db, "users")
        self.assertEqual(dave["name"], "Dave")
        self.assertIsNone(eve)
        _ok("All 2 operations rolled back correctly — no partial state remains.")


# ══════════════════════════════════════════════════════════════════════
# CONSISTENCY
# ══════════════════════════════════════════════════════════════════════

class TestConsistency(unittest.TestCase):

    def _assert_consistent(self, db, table_name):
        table    = db.get_table(table_name)
        rec_keys = set(table.records.keys())
        idx_keys = {k for k, _ in table.bplustree.get_all()}
        _step(f"records dict  keys : {sorted(rec_keys)}")
        _step(f"B+ Tree index keys : {sorted(idx_keys)}")
        for key in rec_keys:
            self.assertIsNotNone(table.bplustree.search(key),
                msg=f"Key {key} in records dict but missing from B+ Tree index!")
        for key in idx_keys:
            self.assertIn(key, table.records,
                msg=f"Key {key} in B+ Tree index but missing from records dict!")
        _step(f"Both sets identical: {'YES ✔' if rec_keys == idx_keys else 'NO ✘'}")

    def test_consistency_after_insert(self):
        _banner("CONSISTENCY  ·  index matches records after insert")
        _section("Setup & Action")
        db = fresh_db()
        _step("Inserting key=5, name='Frank' (committed single-op transaction).")
        _step("_raw_insert() updates records dict AND bplustree.insert() atomically.")
        db.insert_record("users", 5, {"id": 5, "name": "Frank"})
        _section("Consistency Check: records dict ↔ B+ Tree index")
        self._assert_consistent(db, "users")
        _ok("Index and records dict are perfectly in sync after insert.")

    def test_consistency_after_commit(self):
        _banner("CONSISTENCY  ·  index matches records after explicit commit")
        _section("Setup & Action")
        db  = fresh_db()
        txn = db.begin_transaction()
        _step("Staging insert(key=6, name='Grace') inside explicit transaction.")
        _step("After transactional_insert(), _raw_insert() has already run in memory.")
        db.get_table("users").transactional_insert(txn, 6, {"id": 6, "name": "Grace"})
        _step("Calling commit() → COMMIT record written to WAL + fsync.")
        db.commit(txn)
        _section("Consistency Check")
        self._assert_consistent(db, "users")
        _ok("Explicit commit: index and records dict remain in sync.")

    def test_consistency_after_rollback(self):
        _banner("CONSISTENCY  ·  index matches records after rollback")
        _section("Setup")
        db = fresh_db()
        db.insert_record("users", 7, {"id": 7, "name": "Hank"})
        _step("Committed baseline: key=7, name='Hank'.")
        _section("Action: update then ROLLBACK")
        txn = db.begin_transaction()
        db.get_table("users").transactional_update(txn, 7, {"id": 7, "name": "Henry"})
        _step("In-memory record temporarily shows 'Henry'.")
        db.rollback(txn)
        _step("Rollback restores 'Hank'. B+ Tree key 7 was never removed — stays intact.")
        _section("Consistency Check")
        self._assert_consistent(db, "users")
        _ok("After rollback: index and records dict are still in sync.")

    def test_consistency_after_crash_simulation(self):
        _banner("CONSISTENCY  ·  index matches records after crash + recovery")
        if os.path.exists(WAL_PATH):
            os.remove(WAL_PATH)
        _section("Session 1 – normal operation + simulated crash")
        db = DatabaseManager("testdb", log_path=WAL_PATH, auto_recover=False)
        db.create_table("users", "id", order=4)
        _step("Inserting key=20 ('Ivan') and committing — this is durable.")
        db.insert_record("users", 20, {"id": 20, "name": "Ivan"})
        _step("Beginning a NEW transaction: inserting key=21 ('Judy').")
        txn = db.begin_transaction()
        db.get_table("users").transactional_insert(txn, 21, {"id": 21, "name": "Judy"})
        _step("*** CRASH SIMULATED — commit() is never called. ***")
        _step("WAL has BEGIN + INSERT(21) but NO COMMIT for that transaction.")
        _wal_snapshot(db)
        _section("Session 2 – restart with auto_recover=True")
        _step("create_table() triggers TransactionManager.recover():")
        _step("  Phase 1 (Analysis) : txn with COMMIT → committed. txn with no COMMIT → incomplete.")
        _step("  Phase 2 (Redo)     : re-apply INSERT(20) for committed txn.")
        _step("  Phase 3 (Undo)     : undo INSERT(21) → _raw_delete(21) removes the ghost row.")
        db2 = DatabaseManager("testdb", log_path=WAL_PATH, auto_recover=True)
        db2.create_table("users", "id", order=4)
        _section("Consistency Check after recovery")
        ivan = db2.get_table("users").search(20)
        judy = db2.get_table("users").search(21)
        _result("key=20 (Ivan) present", ivan is not None,  good=(ivan is not None))
        _result("key=21 (Judy) present", judy is not None,  good=(judy is None))
        self._assert_consistent(db2, "users")
        _ok("After crash + recovery: index and records dict are in sync.")


# ══════════════════════════════════════════════════════════════════════
# DURABILITY
# ══════════════════════════════════════════════════════════════════════

class TestDurability(unittest.TestCase):

    def test_committed_data_survives_restart(self):
        _banner("DURABILITY  ·  committed data survives restart")
        if os.path.exists(WAL_PATH):
            os.remove(WAL_PATH)
        _section("Session 1 – insert and commit two records")
        db1 = DatabaseManager("durdb", log_path=WAL_PATH, auto_recover=False)
        db1.create_table("products", "id", order=4)
        _step("INSERT key=100 ('Widget') → WAL: BEGIN, INSERT, COMMIT + fsync.")
        db1.insert_record("products", 100, {"id": 100, "name": "Widget", "price": 9.99})
        _step("INSERT key=101 ('Gadget') → WAL: BEGIN, INSERT, COMMIT + fsync.")
        db1.insert_record("products", 101, {"id": 101, "name": "Gadget", "price": 19.99})
        _step(f"WAL now has {len(db1._wal.get_records())} records (all durable on disk).")
        _wal_snapshot(db1)
        _step("Simulating shutdown: deleting the in-memory DatabaseManager object.")
        del db1
        _section("Session 2 – cold restart, no in-memory state")
        _step("Opening a brand-new DatabaseManager with auto_recover=True.")
        _step("create_table() triggers recovery: REDO replays INSERT(100) and INSERT(101).")
        db2 = DatabaseManager("durdb", log_path=WAL_PATH, auto_recover=True)
        db2.create_table("products", "id", order=4)
        _section("Verification")
        r100 = db2.get_table("products").search(100)
        r101 = db2.get_table("products").search(101)
        _result("key=100 recovered", r100)
        _result("key=101 recovered", r101)
        _result("r100['name']", r100["name"] if r100 else "—")
        _result("r101['name']", r101["name"] if r101 else "—")
        _table_snapshot(db2, "products")
        self.assertIsNotNone(r100, "Record 100 should survive restart")
        self.assertIsNotNone(r101, "Record 101 should survive restart")
        self.assertEqual(r100["name"], "Widget")
        self.assertEqual(r101["name"], "Gadget")
        _ok("Both committed records survived the simulated restart via WAL REDO.")

    def test_uncommitted_data_not_present_after_restart(self):
        _banner("DURABILITY  ·  uncommitted data absent after restart")
        if os.path.exists(WAL_PATH):
            os.remove(WAL_PATH)
        _section("Session 1 – one committed record + one partial (crashed) transaction")
        db1 = DatabaseManager("durdb2", log_path=WAL_PATH, auto_recover=False)
        db1.create_table("orders", "id", order=4)
        _step("INSERT key=1 ('Book') → committed. WAL: BEGIN, INSERT, COMMIT.")
        db1.insert_record("orders", 1, {"id": 1, "item": "Book"})
        _step("Begin txn for key=2 ('Pen') → WAL: BEGIN, INSERT.  No COMMIT written.")
        txn = db1.begin_transaction()
        db1.get_table("orders").transactional_insert(txn, 2, {"id": 2, "item": "Pen"})
        _step("*** CRASH — process dies here.  COMMIT never written. ***")
        _wal_snapshot(db1)
        del db1
        _section("Session 2 – restart and recover")
        _step("Recovery analysis:")
        _step("  txn for key=1 has COMMIT  → 'committed' set → REDO.")
        _step("  txn for key=2 has no COMMIT → 'incomplete' set → UNDO.")
        _step("Redo : _raw_insert(1, {'item':'Book'}).")
        _step("Undo : _raw_delete(2)  — removes the ghost row for 'Pen'.")
        db2 = DatabaseManager("durdb2", log_path=WAL_PATH, auto_recover=True)
        db2.create_table("orders", "id", order=4)
        _section("Verification")
        r1 = db2.get_table("orders").search(1)
        r2 = db2.get_table("orders").search(2)
        _result("key=1 (Book) present after restart", r1 is not None, good=(r1 is not None))
        _result("key=2 (Pen)  present after restart", r2 is not None, good=(r2 is None))
        _table_snapshot(db2, "orders")
        self.assertIsNotNone(r1, "Committed record should exist after recovery")
        self.assertIsNone(r2,    "Uncommitted record must not appear after recovery")
        _ok("REDO restored the committed record; UNDO erased the partial one.")


# ══════════════════════════════════════════════════════════════════════
# INDEX CONSISTENCY
# ══════════════════════════════════════════════════════════════════════

class TestIndexConsistency(unittest.TestCase):

    def setUp(self):
        if os.path.exists(WAL_PATH):
            os.remove(WAL_PATH)
        self.db = DatabaseManager("idxtest", log_path=WAL_PATH, auto_recover=False)
        self.db.create_table("t", "id", order=4)

    def _idx_keys(self):
        return {k for k, _ in self.db.get_table("t").bplustree.get_all()}

    def _rec_keys(self):
        return set(self.db.get_table("t").records.keys())

    def _print_state(self, label):
        idx = sorted(self._idx_keys())
        rec = sorted(self._rec_keys())
        _step(f"{label}")
        _step(f"  records dict  : {rec}")
        _step(f"  B+ Tree index : {idx}")
        _step(f"  In sync       : {'YES ✔' if idx == rec else 'NO ✘'}")

    def test_index_matches_records_after_insert(self):
        _banner("INDEX CONSISTENCY  ·  after insert")
        _section("Action")
        _step("insert_record('t', key=1) → _raw_insert() writes to BOTH structures simultaneously.")
        self.db.insert_record("t", 1, {"id": 1})
        _section("State")
        self._print_state("After insert:")
        self.assertEqual(self._idx_keys(), self._rec_keys())
        _ok("Index matches records dict after insert.")

    def test_index_matches_records_after_delete(self):
        _banner("INDEX CONSISTENCY  ·  after delete")
        _section("Action")
        _step("Insert key=1 and key=2, then delete key=1.")
        _step("_raw_delete() removes from records dict AND calls bplustree.delete().")
        self.db.insert_record("t", 1, {"id": 1})
        self.db.insert_record("t", 2, {"id": 2})
        self._print_state("Before delete:")
        self.db.delete_record("t", 1)
        _section("State after delete")
        self._print_state("After delete(key=1):")
        self.assertEqual(self._idx_keys(), self._rec_keys())
        _ok("Index matches records dict after delete.")

    def test_index_matches_records_after_rollback_delete(self):
        _banner("INDEX CONSISTENCY  ·  after rollback of delete")
        _section("Action")
        self.db.insert_record("t", 5, {"id": 5})
        _step("Insert key=5 (committed).")
        self._print_state("Before transactional delete:")
        txn = self.db.begin_transaction()
        self.db.get_table("t").transactional_delete(txn, 5)
        _step("transactional_delete(5) → row removed from both structures temporarily.")
        self._print_state("After delete, before rollback:")
        self.db.rollback(txn)
        _step("rollback() → undo DELETE: _raw_insert(5) re-adds to both structures.")
        _section("State after rollback")
        self._print_state("After rollback:")
        self.assertEqual(self._idx_keys(), self._rec_keys())
        _ok("Rollback of delete restored both records dict and B+ Tree index.")

    def test_index_matches_records_after_failed_insert(self):
        _banner("INDEX CONSISTENCY  ·  after rollback of insert")
        _section("Action")
        self.db.insert_record("t", 9, {"id": 9})
        _step("Insert key=9 (committed baseline).")
        txn = self.db.begin_transaction()
        self.db.get_table("t").transactional_insert(txn, 10, {"id": 10})
        _step("transactional_insert(10) → key=10 added to both structures temporarily.")
        self._print_state("After insert key=10, before rollback:")
        self.db.rollback(txn)
        _step("rollback() → undo INSERT: _raw_delete(10) removes from both structures.")
        _section("State after rollback")
        self._print_state("After rollback:")
        self.assertEqual(self._idx_keys(), self._rec_keys())
        self.assertNotIn(10, self._rec_keys())
        _ok("Rolled-back insert removed from both records dict and B+ Tree index.")


if __name__ == "__main__":
    print("\n" + "═" * W)
    print("  ACID VALIDATION SUITE  –  B+ Tree DBMS Engine")
    print("  Testing: Atomicity · Consistency · Durability · Index Sync")
    print("═" * W)
    unittest.main(verbosity=2, buffer=False)