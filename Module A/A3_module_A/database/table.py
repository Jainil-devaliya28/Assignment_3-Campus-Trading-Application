"""
Table abstraction for the DBMS.
Maps indexed keys to stored records/values.

Now supports two operation layers:
  1. Raw (_raw_*) - direct writes used by recovery/undo; bypass logging.
  2. Transactional - all normal operations must go through a Transaction
     object so changes are logged and atomically committed or rolled back.
"""

from typing import Any, List, Tuple, Optional, Dict
from .bplustree import BPlusTree


class Table:
    """Represents a database table with B+ Tree indexing."""

    def __init__(self, table_name: str, index_column: str, order: int = 3):
        self.table_name   = table_name
        self.index_column = index_column
        self.bplustree    = BPlusTree(order=order)
        self.records: Dict[int, Dict] = {}
        self.schema: Dict[str, str]   = {}

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def define_schema(self, schema: Dict[str, str]) -> None:
        self.schema = schema

    # ------------------------------------------------------------------
    # RAW operations (no logging - used by recovery / undo internals)
    # ------------------------------------------------------------------

    def _raw_insert(self, key: int, record: Dict) -> None:
        """Direct insert that bypasses the transaction layer."""
        self.records[key] = record
        self.bplustree.insert(key, key)

    def _raw_update(self, key: int, record: Dict) -> None:
        """Direct update that bypasses the transaction layer."""
        self.records[key] = record
        self.bplustree.update(key, key)

    def _raw_delete(self, key: int) -> None:
        """Direct delete that bypasses the transaction layer."""
        if key in self.records:
            del self.records[key]
            self.bplustree.delete(key)

    # ------------------------------------------------------------------
    # TRANSACTIONAL operations (all normal callers should use these)
    # ------------------------------------------------------------------

    def transactional_insert(self, txn, key: int, record: Dict) -> None:
        """
        Insert a record inside a transaction.

        1. Stage the op in the WAL via txn.stage_insert().
        2. Apply immediately so the change is visible within this txn.
        (Undo is available via txn.abort() → _raw_delete.)
        """
        if key in self.records:
            raise ValueError(f"Key {key} already exists in '{self.table_name}'")
        txn.stage_insert(self.table_name, key, record)
        self._raw_insert(key, record)

    def transactional_update(self, txn, key: int, new_record: Dict) -> None:
        """
        Update a record inside a transaction.

        Captures the before-image so abort() can restore it.
        """
        if key not in self.records:
            raise KeyError(f"Key {key} not found in '{self.table_name}'")
        old_record = dict(self.records[key])   # snapshot before-image
        txn.stage_update(self.table_name, key, old_record, new_record)
        self._raw_update(key, new_record)

    def transactional_delete(self, txn, key: int) -> None:
        """
        Delete a record inside a transaction.

        Captures the before-image so abort() can restore it.
        """
        if key not in self.records:
            raise KeyError(f"Key {key} not found in '{self.table_name}'")
        old_record = dict(self.records[key])
        txn.stage_delete(self.table_name, key, old_record)
        self._raw_delete(key)

    # ------------------------------------------------------------------
    # Read operations (no logging needed)
    # ------------------------------------------------------------------

    def search(self, key: int) -> Optional[Dict]:
        result = self.bplustree.search(key)
        if result is not None:
            return self.records.get(result)
        return None

    def range_query(self, start_key: int, end_key: int) -> List[Dict]:
        results = []
        for key, _ in self.bplustree.range_query(start_key, end_key):
            if key in self.records:
                results.append(self.records[key])
        return results

    def get_all(self) -> List[Dict]:
        results = []
        for key, _ in self.bplustree.get_all():
            if key in self.records:
                results.append(self.records[key])
        return results

    def count(self) -> int:
        return len(self.records)

    # ------------------------------------------------------------------
    # Legacy non-transactional helpers (kept for backward compatibility)
    # ------------------------------------------------------------------

    def insert(self, key: int, record: Dict) -> None:
        """Non-transactional insert (use transactional_insert in new code)."""
        self._raw_insert(key, record)

    def update(self, key: int, new_record: Dict) -> bool:
        if key not in self.records:
            return False
        self._raw_update(key, new_record)
        return True

    def delete(self, key: int) -> bool:
        if key not in self.records:
            return False
        self._raw_delete(key)
        return True

    def __repr__(self):
        return f"Table(name={self.table_name}, records={len(self.records)})"
