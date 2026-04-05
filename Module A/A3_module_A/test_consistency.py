import os
import unittest
from db_test_utils import _banner, _section, _step, _result, _ok, _wal_snapshot, _table_snapshot, fresh_db, WAL_PATH
from database.db_manager import DatabaseManager

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

if __name__ == "__main__":
    unittest.main(verbosity=2)