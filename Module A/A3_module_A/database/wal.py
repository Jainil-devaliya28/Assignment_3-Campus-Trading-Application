"""
Write-Ahead Log (WAL) - Persistent logging for crash recovery.

Every change is first written to the log BEFORE it touches the actual data.
On restart, the log is replayed to restore committed transactions and
undo any that never finished.

Log record format (one per line in the .wal file):
  <LSN>|<TXN_ID>|<RECORD_TYPE>|<TABLE>|<KEY>|<OLD_VALUE>|<NEW_VALUE>

Record types:
  BEGIN      - transaction started
  INSERT     - row was inserted
  UPDATE     - row was updated
  DELETE     - row was deleted
  COMMIT     - transaction committed
  ABORT      - transaction aborted / rolled back
  CHECKPOINT - stable point; everything before this LSN is durable
"""

import os
import json
import threading
from enum import Enum
from typing import Optional, Any, List
from dataclasses import dataclass, field


class LogRecordType(Enum):
    BEGIN      = "BEGIN"
    INSERT     = "INSERT"
    UPDATE     = "UPDATE"
    DELETE     = "DELETE"
    COMMIT     = "COMMIT"
    ABORT      = "ABORT"
    CHECKPOINT = "CHECKPOINT"


@dataclass
class LogRecord:
    lsn: int                          # Log Sequence Number - monotonically increasing
    txn_id: int
    record_type: LogRecordType
    table_name: Optional[str] = None
    key: Optional[int] = None
    old_value: Optional[Any] = None   # Before-image (needed for UNDO)
    new_value: Optional[Any] = None   # After-image  (needed for REDO)

    def serialize(self) -> str:
        """Convert to a single pipe-delimited log line."""
        old_json = json.dumps(self.old_value) if self.old_value is not None else "null"
        new_json = json.dumps(self.new_value) if self.new_value is not None else "null"
        table   = self.table_name or ""
        key_str = str(self.key) if self.key is not None else ""
        return f"{self.lsn}|{self.txn_id}|{self.record_type.value}|{table}|{key_str}|{old_json}|{new_json}\n"

    @staticmethod
    def deserialize(line: str) -> "LogRecord":
        """Parse one log line back into a LogRecord."""
        parts = line.strip().split("|", 6)
        lsn, txn_id, rtype, table, key_str, old_json, new_json = parts

        old_val = json.loads(old_json)
        new_val = json.loads(new_json)
        key     = int(key_str) if key_str else None
        table   = table if table else None

        return LogRecord(
            lsn=int(lsn),
            txn_id=int(txn_id),
            record_type=LogRecordType(rtype),
            table_name=table,
            key=key,
            old_value=old_val,
            new_value=new_val,
        )


class WriteAheadLog:
    """
    Thread-safe Write-Ahead Log backed by a flat file.

    Usage pattern
    -------------
    wal = WriteAheadLog("mydb.wal")
    lsn = wal.append(LogRecord(lsn=0, txn_id=1, record_type=LogRecordType.BEGIN))
    # … data changes …
    wal.append(LogRecord(lsn=0, txn_id=1, record_type=LogRecordType.COMMIT))
    wal.flush()   # fsync to disk
    """

    def __init__(self, log_path: str = "database.wal"):
        self.log_path   = log_path
        self._lock      = threading.Lock()
        self._lsn       = 0            # next LSN to assign
        self._records: List[LogRecord] = []  # in-memory buffer
        self._load_existing_log()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_existing_log(self):
        """Read an existing WAL file on startup (for recovery)."""
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = LogRecord.deserialize(line)
                    self._records.append(rec)
                    self._lsn = max(self._lsn, rec.lsn + 1)
                except Exception:
                    # Truncated / corrupt tail - stop reading
                    break

    def _next_lsn(self) -> int:
        lsn = self._lsn
        self._lsn += 1
        return lsn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, record: LogRecord) -> int:
        """
        Assign a real LSN to *record*, persist it to disk, and return the LSN.
        This is called BEFORE the actual data structure is modified.
        """
        with self._lock:
            record.lsn = self._next_lsn()
            self._records.append(record)
            # Force-append to file immediately (write-ahead guarantee)
            with open(self.log_path, "a") as f:
                f.write(record.serialize())
            return record.lsn

    def flush(self):
        """fsync the log file (guarantees OS page-cache → disk)."""
        with self._lock:
            with open(self.log_path, "a") as f:
                f.flush()
                os.fsync(f.fileno())

    def get_records(self) -> List[LogRecord]:
        """Return all in-memory log records (used by recovery)."""
        with self._lock:
            return list(self._records)

    def checkpoint(self, txn_id: int = -1):
        """
        Write a CHECKPOINT record.  Everything before the checkpoint LSN
        is considered durable and won't need re-analysis on restart.
        """
        rec = LogRecord(lsn=0, txn_id=txn_id, record_type=LogRecordType.CHECKPOINT)
        self.append(rec)
        self.flush()

    def clear(self):
        """Wipe the log file (called after a successful checkpoint)."""
        with self._lock:
            self._records.clear()
            if os.path.exists(self.log_path):
                os.remove(self.log_path)

    def __len__(self):
        return len(self._records)
