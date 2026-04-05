"""
Database Manager - manages tables and database-wide operations.

Now wires in the Write-Ahead Log and Transaction Manager so every
mutating operation goes through ACID-safe transactions.
"""

from typing import Dict, Optional, List, Any
from .table import Table
from .wal import WriteAheadLog
from .transaction_manager import TransactionManager


class DatabaseManager:
    """Manages database tables and operations with full ACID support."""

    def __init__(self, db_name: str, log_path: Optional[str] = None, auto_recover: bool = True):
        """
        Initialize the database manager.

        Args:
            db_name      : Logical name of the database.
            log_path     : Path to the WAL file.  Defaults to '<db_name>.wal'.
            auto_recover : If True, run crash recovery on startup.
        """
        self.db_name = db_name
        self.tables: Dict[str, Table] = {}

        # Initialise WAL
        wal_path  = log_path or f"{db_name}.wal"
        self._wal = WriteAheadLog(wal_path)

        # Initialise TransactionManager (shares reference to self.tables)
        self._txn_mgr = TransactionManager(self._wal, self.tables)

        # auto_recover is stored; actual recovery runs after tables are
        # registered via recover() or the first create_table call.
        self._auto_recover        = auto_recover
        self._recovery_report: Dict = {}
        self._recovered           = False

    # ------------------------------------------------------------------
    # Transaction API (exposed to callers)
    # ------------------------------------------------------------------

    def begin_transaction(self):
        """Start and return a new Transaction object."""
        return self._txn_mgr.begin()

    def commit(self, txn) -> None:
        """Commit a transaction."""
        self._txn_mgr.commit(txn)

    def rollback(self, txn) -> None:
        """Abort / roll back a transaction."""
        self._txn_mgr.abort(txn)

    # ------------------------------------------------------------------
    # Convenience transactional helpers
    # ------------------------------------------------------------------

    def insert_record(self, table_name: str, key: int, record: Dict) -> None:
        """Insert a record using an auto-managed single-op transaction."""
        table = self._get_table_or_raise(table_name)
        txn   = self.begin_transaction()
        try:
            table.transactional_insert(txn, key, record)
            self.commit(txn)
        except Exception:
            self.rollback(txn)
            raise

    def update_record(self, table_name: str, key: int, new_record: Dict) -> None:
        """Update a record using an auto-managed single-op transaction."""
        table = self._get_table_or_raise(table_name)
        txn   = self.begin_transaction()
        try:
            table.transactional_update(txn, key, new_record)
            self.commit(txn)
        except Exception:
            self.rollback(txn)
            raise

    def delete_record(self, table_name: str, key: int) -> None:
        """Delete a record using an auto-managed single-op transaction."""
        table = self._get_table_or_raise(table_name)
        txn   = self.begin_transaction()
        try:
            table.transactional_delete(txn, key)
            self.commit(txn)
        except Exception:
            self.rollback(txn)
            raise

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def create_table(self, table_name: str, index_column: str, order: int = 3) -> Table:
        if table_name in self.tables:
            raise ValueError(f"Table '{table_name}' already exists")
        table = Table(table_name, index_column, order=order)
        self.tables[table_name] = table
        # Run deferred recovery the first time tables are available
        if self._auto_recover and not self._recovered:
            self._recovered = True
            self._recovery_report = self._txn_mgr.recover(self.tables)
            if self._recovery_report.get("redone") or self._recovery_report.get("undone"):
                print(f"[DatabaseManager] Recovery complete: {self._recovery_report}")
        return table

    def get_table(self, table_name: str) -> Optional[Table]:
        return self.tables.get(table_name)

    def drop_table(self, table_name: str) -> bool:
        if table_name in self.tables:
            del self.tables[table_name]
            return True
        return False

    def list_tables(self) -> List[str]:
        return list(self.tables.keys())

    def checkpoint(self) -> None:
        """Write a WAL checkpoint (marks durable point in log)."""
        self._wal.checkpoint()

    def get_database_stats(self) -> Dict[str, Any]:
        stats = {
            "db_name": self.db_name,
            "num_tables": len(self.tables),
            "wal_records": len(self._wal),
            "active_transactions": self._txn_mgr.active_transactions(),
            "tables": {},
        }
        for name, table in self.tables.items():
            stats["tables"][name] = {
                "record_count": table.count(),
                "index_column": table.index_column,
            }
        return stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_table_or_raise(self, table_name: str) -> Table:
        table = self.tables.get(table_name)
        if table is None:
            raise KeyError(f"Table '{table_name}' does not exist")
        return table

    def __repr__(self):
        return f"DatabaseManager(db='{self.db_name}', tables={list(self.tables.keys())})"
