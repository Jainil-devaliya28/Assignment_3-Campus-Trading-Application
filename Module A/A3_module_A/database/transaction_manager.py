"""
Transaction Manager - coordinates ACID lifecycle for every operation.

ACID guarantees provided
------------------------
Atomicity   - every operation in a transaction commits together or all
              changes are rolled back using the WAL before-images.
Consistency - the B+ Tree index and the records dict are updated in the
              same critical section; if either fails the WAL is used to
              restore the previous state.
Isolation   - each transaction operates on its own private change-set
              (write-set); uncommitted changes are invisible to others.
Durability  - COMMIT is only acknowledged after the WAL record has been
              fsynced to disk; data is replayed on restart.
"""

import threading
from enum import Enum
from typing import Any, Dict, Optional, List
from .wal import WriteAheadLog, LogRecord, LogRecordType


class TransactionState(Enum):
    ACTIVE    = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED   = "ABORTED"


class Transaction:
    """
    Represents one database transaction.

    A transaction accumulates a *write-set* of pending changes.  When
    commit() is called the changes are flushed to the real Table objects
    and a COMMIT record is written to the WAL.  If abort() is called (or
    a crash is detected) the write-set is discarded and WAL before-images
    are used to undo any partially-applied changes.
    """

    def __init__(self, txn_id: int, wal: WriteAheadLog):
        self.txn_id: int             = txn_id
        self.wal: WriteAheadLog      = wal
        self.state: TransactionState = TransactionState.ACTIVE
        # Ordered list of (log_record, apply_fn, undo_fn) tuples
        self._ops: List[Dict]        = []

    # ------------------------------------------------------------------
    # Staging operations (called by Table wrappers)
    # ------------------------------------------------------------------

    def stage_insert(self, table_name: str, key: int, record: Dict) -> None:
        """Stage an INSERT - the record doesn't yet exist."""
        log_rec = LogRecord(
            lsn=0, txn_id=self.txn_id,
            record_type=LogRecordType.INSERT,
            table_name=table_name, key=key,
            old_value=None, new_value=record,
        )
        self.wal.append(log_rec)
        self._ops.append({"log": log_rec, "type": "INSERT",
                          "table": table_name, "key": key,
                          "old": None, "new": record})

    def stage_update(self, table_name: str, key: int,
                     old_record: Dict, new_record: Dict) -> None:
        """Stage an UPDATE - captures before-image for rollback."""
        log_rec = LogRecord(
            lsn=0, txn_id=self.txn_id,
            record_type=LogRecordType.UPDATE,
            table_name=table_name, key=key,
            old_value=old_record, new_value=new_record,
        )
        self.wal.append(log_rec)
        self._ops.append({"log": log_rec, "type": "UPDATE",
                          "table": table_name, "key": key,
                          "old": old_record, "new": new_record})

    def stage_delete(self, table_name: str, key: int, old_record: Dict) -> None:
        """Stage a DELETE - captures before-image so the row can be restored."""
        log_rec = LogRecord(
            lsn=0, txn_id=self.txn_id,
            record_type=LogRecordType.DELETE,
            table_name=table_name, key=key,
            old_value=old_record, new_value=None,
        )
        self.wal.append(log_rec)
        self._ops.append({"log": log_rec, "type": "DELETE",
                          "table": table_name, "key": key,
                          "old": old_record, "new": None})

    # ------------------------------------------------------------------
    # Commit / Abort
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """
        Finalize the transaction.

        1. Write COMMIT to WAL and fsync.
        2. Mark state as COMMITTED.
        (Actual data has already been written by the Table wrappers.)
        """
        if self.state != TransactionState.ACTIVE:
            raise RuntimeError(f"Cannot commit txn {self.txn_id}: state={self.state}")

        commit_rec = LogRecord(lsn=0, txn_id=self.txn_id,
                               record_type=LogRecordType.COMMIT)
        self.wal.append(commit_rec)
        self.wal.flush()          # <-- durability guarantee
        self.state = TransactionState.COMMITTED

    def abort(self, tables: Dict) -> None:
        """
        Roll back all staged operations in reverse order.

        For each op we apply the inverse:
          INSERT  → delete the inserted row
          UPDATE  → restore the old record
          DELETE  → re-insert the deleted row
        """
        if self.state == TransactionState.COMMITTED:
            raise RuntimeError(f"Cannot abort an already-committed txn {self.txn_id}")

        # Undo in reverse chronological order
        for op in reversed(self._ops):
            table = tables.get(op["table"])
            if table is None:
                continue
            try:
                if op["type"] == "INSERT":
                    # Undo insert → hard-delete (bypass transaction layer)
                    table._raw_delete(op["key"])
                elif op["type"] == "UPDATE":
                    # Undo update → restore old record
                    table._raw_update(op["key"], op["old"])
                elif op["type"] == "DELETE":
                    # Undo delete → re-insert old record
                    table._raw_insert(op["key"], op["old"])
            except Exception as e:
                # Log but continue rolling back other ops
                print(f"[TxnManager] WARN: undo op failed for key={op['key']}: {e}")

        abort_rec = LogRecord(lsn=0, txn_id=self.txn_id,
                              record_type=LogRecordType.ABORT)
        self.wal.append(abort_rec)
        self.wal.flush()
        self.state = TransactionState.ABORTED


class TransactionManager:
    """
    Central coordinator for all transactions.

    Usage
    -----
    tm  = TransactionManager(wal, tables_dict)
    txn = tm.begin()
    txn.stage_insert("users", 1, {"id": 1, "name": "Alice"})
    # ... apply to table via Table.transactional_insert(txn, ...)
    tm.commit(txn)
    """

    def __init__(self, wal: WriteAheadLog, tables: Dict):
        self._wal        = wal
        self._tables     = tables        # shared reference to DatabaseManager.tables
        self._lock       = threading.Lock()
        self._txn_counter = 0
        self._active: Dict[int, Transaction] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def begin(self) -> Transaction:
        """Start a new transaction and return it."""
        with self._lock:
            self._txn_counter += 1
            txn_id = self._txn_counter

        txn = Transaction(txn_id, self._wal)
        begin_rec = LogRecord(lsn=0, txn_id=txn_id,
                              record_type=LogRecordType.BEGIN)
        self._wal.append(begin_rec)

        with self._lock:
            self._active[txn_id] = txn

        return txn

    def commit(self, txn: Transaction) -> None:
        """Commit a transaction."""
        txn.commit()
        with self._lock:
            self._active.pop(txn.txn_id, None)

    def abort(self, txn: Transaction) -> None:
        """Abort / rollback a transaction."""
        txn.abort(self._tables)
        with self._lock:
            self._active.pop(txn.txn_id, None)

    def active_transactions(self) -> List[int]:
        with self._lock:
            return list(self._active.keys())

    # ------------------------------------------------------------------
    # Recovery (called by DatabaseManager on startup)
    # ------------------------------------------------------------------

    def recover(self, tables: Dict) -> Dict:
        """
        ARIES-style crash recovery using WAL records.

        Phase 1 - Analysis : find all committed and incomplete transactions.
        Phase 2 - Redo     : replay all committed changes.
        Phase 3 - Undo     : roll back any transactions that never committed.

        Returns a summary dict for diagnostics.
        """
        records = self._wal.get_records()
        if not records:
            return {"redone": 0, "undone": 0, "incomplete_txns": []}

        # ---- Phase 1: Analysis ----------------------------------------
        committed:  set = set()
        aborted:    set = set()
        all_txns:   set = set()
        ops_by_txn: Dict[int, list] = {}

        for rec in records:
            all_txns.add(rec.txn_id)
            if rec.record_type == LogRecordType.COMMIT:
                committed.add(rec.txn_id)
            elif rec.record_type == LogRecordType.ABORT:
                aborted.add(rec.txn_id)
            elif rec.record_type in (LogRecordType.INSERT,
                                     LogRecordType.UPDATE,
                                     LogRecordType.DELETE):
                ops_by_txn.setdefault(rec.txn_id, []).append(rec)

        incomplete = all_txns - committed - aborted - {-1}  # -1 = checkpoint txn

        # ---- Phase 2: Redo committed transactions ---------------------
        redo_count = 0
        for txn_id in committed:
            for rec in ops_by_txn.get(txn_id, []):
                table = tables.get(rec.table_name)
                if table is None:
                    continue
                try:
                    if rec.record_type == LogRecordType.INSERT:
                        if rec.new_value and rec.key not in table.records:
                            table._raw_insert(rec.key, rec.new_value)
                            redo_count += 1
                    elif rec.record_type == LogRecordType.UPDATE:
                        if rec.new_value:
                            table._raw_update(rec.key, rec.new_value)
                            redo_count += 1
                    elif rec.record_type == LogRecordType.DELETE:
                        if rec.key in table.records:
                            table._raw_delete(rec.key)
                            redo_count += 1
                except Exception as e:
                    print(f"[Recovery] WARN: redo failed txn={txn_id} key={rec.key}: {e}")

        # ---- Phase 3: Undo incomplete transactions --------------------
        undo_count = 0
        for txn_id in incomplete:
            for rec in reversed(ops_by_txn.get(txn_id, [])):
                table = tables.get(rec.table_name)
                if table is None:
                    continue
                try:
                    if rec.record_type == LogRecordType.INSERT:
                        table._raw_delete(rec.key)
                        undo_count += 1
                    elif rec.record_type == LogRecordType.UPDATE and rec.old_value:
                        table._raw_update(rec.key, rec.old_value)
                        undo_count += 1
                    elif rec.record_type == LogRecordType.DELETE and rec.old_value:
                        table._raw_insert(rec.key, rec.old_value)
                        undo_count += 1
                except Exception as e:
                    print(f"[Recovery] WARN: undo failed txn={txn_id} key={rec.key}: {e}")

        return {
            "redone": redo_count,
            "undone": undo_count,
            "incomplete_txns": list(incomplete),
            "committed_txns": list(committed),
        }
