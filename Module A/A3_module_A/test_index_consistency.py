import os
import unittest
from db_test_utils import _banner, _section, _step, _result, _ok, WAL_PATH
from database.db_manager import DatabaseManager

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
    unittest.main(verbosity=2)